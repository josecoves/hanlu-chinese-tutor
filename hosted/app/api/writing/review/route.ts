import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../../chatgpt-auth";
import content from "../../../hanlu-data.json";

export const dynamic = "force-dynamic";

const VALID_MODES = new Set(["prompt", "message", "translation", "guided"]);
const DAILY_REQUEST_LIMIT = 35;
const DAILY_BUDGET_MICRO_USD = 20_000;
const REQUEST_RESERVATION_MICRO_USD = 500;
const MINUTE_REQUEST_LIMIT = 4;

type RuntimeEnv = {
  DB: {
    prepare(query: string): {
      bind(...values: unknown[]): {
        first<T>(): Promise<T | null>;
        run(): Promise<unknown>;
      };
    };
  };
  DEEPSEEK_API_KEY?: string;
  DEEPSEEK_MODEL?: string;
};

type Feedback = {
  verdict: "clear" | "needs_revision";
  summary: string;
  taskCompletion: { status: string; feedback: string };
  grammarWordOrder: { status: string; feedback: string };
  vocabularyNaturalness: { status: string; feedback: string };
  charactersTyping: { status: string; feedback: string };
  placeholders: Array<{
    english: string;
    chinese: string;
    pinyin: string;
    hskLevel: string;
    note: string;
  }>;
  correctedChinese: string;
  changes: Array<{ original: string; replacement: string; reason: string }>;
  revisionPrompt: string;
};

function error(message: string, status: number) {
  return NextResponse.json({ error: message }, { status });
}

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return error("Sign in is required to review writing.", 401);

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return error("The writing request could not be read.", 400);
  }

  const attemptId =
    typeof body.attemptId === "string" && /^[a-zA-Z0-9-]{8,80}$/.test(body.attemptId)
      ? body.attemptId
      : crypto.randomUUID();
  const mode = typeof body.mode === "string" ? body.mode : "";
  const hskLevel = Number(body.hskLevel);
  const promptText = typeof body.promptText === "string" ? body.promptText.trim() : "";
  const responseText = typeof body.responseText === "string" ? body.responseText.trim() : "";
  const targetWords = Array.isArray(body.targetWords)
    ? body.targetWords.filter((word): word is string => typeof word === "string").slice(0, 8)
    : [];

  if (!VALID_MODES.has(mode) || ![1, 2].includes(hskLevel)) {
    return error("Choose a valid writing mode and HSK level.", 400);
  }
  if (!promptText || !responseText) {
    return error("Write a response before asking for feedback.", 400);
  }
  if (promptText.length > 2_000 || responseText.length > 5_000) {
    return error("This draft is too long for the focused writing reviewer.", 413);
  }

  const { env } = await import("cloudflare:workers");
  const runtime = env as unknown as RuntimeEnv;
  const apiKey = runtime.DEEPSEEK_API_KEY;
  if (!apiKey) {
    return error(
      "AI review is ready but not configured on this private site. Your draft is still saved on this device.",
      503,
    );
  }

  const now = new Date();
  const nowIso = now.toISOString();
  const usageDate = nowIso.slice(0, 10);
  const minuteAgo = new Date(now.getTime() - 60_000).toISOString();
  const usage = await runtime.DB.prepare(
    `SELECT COUNT(*) AS requests,
            COALESCE(SUM(reserved_micro_usd), 0) AS reserved
       FROM writing_ai_usage
      WHERE usage_date = ?`,
  )
    .bind(usageDate)
    .first<{ requests: number; reserved: number }>();
  const recent = await runtime.DB.prepare(
    `SELECT COUNT(*) AS requests
       FROM writing_ai_usage
      WHERE user_id = ? AND created_at >= ?`,
  )
    .bind(user.id, minuteAgo)
    .first<{ requests: number }>();

  if (Number(recent?.requests ?? 0) >= MINUTE_REQUEST_LIMIT) {
    return error("Please wait a minute before requesting another review.", 429);
  }
  if (
    Number(usage?.requests ?? 0) >= DAILY_REQUEST_LIMIT ||
    Number(usage?.reserved ?? 0) + REQUEST_RESERVATION_MICRO_USD > DAILY_BUDGET_MICRO_USD
  ) {
    return error("Hanlu's small daily AI allowance has been reached. Try again tomorrow.", 429);
  }

  const reservationId = crypto.randomUUID();
  await runtime.DB.prepare(
    `INSERT INTO writing_ai_usage
       (id, user_id, usage_date, reserved_micro_usd, status, created_at)
     VALUES (?, ?, ?, ?, 'reserved', ?)`,
  )
    .bind(
      reservationId,
      user.id,
      usageDate,
      REQUEST_RESERVATION_MICRO_USD,
      nowIso,
    )
    .run();

  const systemPrompt = buildSystemPrompt(hskLevel);
  const userPrompt = JSON.stringify({
    mode,
    target_level: `HSK ${hskLevel}`,
    task: promptText,
    target_words: targetWords,
    learner_answer: responseText,
  });

  try {
    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: runtime.DEEPSEEK_MODEL || "deepseek-chat",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        response_format: { type: "json_object" },
        max_tokens: 1_100,
        temperature: 0.2,
      }),
    });

    if (!response.ok) {
      await markReservation(runtime, reservationId, "provider_error");
      return error("The AI reviewer is temporarily unavailable. Your draft was not lost.", 502);
    }

    const payload = (await response.json()) as {
      choices?: Array<{ message?: { content?: string | null } }>;
    };
    const raw = payload.choices?.[0]?.message?.content;
    if (!raw) {
      await markReservation(runtime, reservationId, "empty_response");
      return error("The reviewer returned an empty answer. Please try once more.", 502);
    }

    const feedback = normalizeFeedback(JSON.parse(raw));
    if (!feedback) {
      await markReservation(runtime, reservationId, "invalid_response");
      return error("The reviewer returned feedback Hanlu could not display safely.", 502);
    }
    enrichPlaceholderLevels(feedback);

    await markReservation(runtime, reservationId, "completed");
    await runtime.DB.prepare(
      `INSERT INTO writing_attempts
         (id, user_id, mode, hsk_level, prompt_text, response_text,
          target_words_json, feedback_json, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         response_text = excluded.response_text,
         feedback_json = excluded.feedback_json,
         updated_at = excluded.updated_at
       WHERE writing_attempts.user_id = excluded.user_id`,
    )
      .bind(
        attemptId,
        user.id,
        mode,
        hskLevel,
        promptText,
        responseText,
        JSON.stringify(targetWords),
        JSON.stringify(feedback),
        nowIso,
        nowIso,
      )
      .run();

    return NextResponse.json({ attemptId, feedback });
  } catch {
    await markReservation(runtime, reservationId, "failed");
    return error("The AI reviewer could not finish. Your draft remains available to revise.", 502);
  }
}

async function markReservation(runtime: RuntimeEnv, id: string, status: string) {
  await runtime.DB.prepare(
    "UPDATE writing_ai_usage SET status = ? WHERE id = ?",
  )
    .bind(status, id)
    .run();
}

function buildSystemPrompt(hskLevel: number) {
  return `You are Hanlu's careful Mandarin writing tutor for an English-speaking learner at HSK ${hskLevel}.
Return only a JSON object matching the schema below. Use concise, neutral English feedback.

The learner is explicitly allowed to place English words or phrases inside otherwise Chinese writing when they do not know the Mandarin. Treat those spans as vocabulary help requests, never as grammar failures. Infer the intended Mandarin, give simplified characters, tone-mark pinyin, a realistic HSK level, and a short usage note. Then assess the Chinese sentence as if the suggested Mandarin had been inserted.

Priorities:
1. Did the answer communicate and complete the task?
2. Is Mandarin word order and grammar correct for the intended meaning?
3. Is vocabulary natural and appropriate at this level?
4. Are there character, punctuation, or typing issues?
Accept natural alternative answers and omitted subjects/objects when context permits. Do not demand the model wording. Distinguish grammar problems from vocabulary, character, punctuation, and style. Do not lower the verdict for a reasonable English placeholder. Keep the corrected version close to the learner's meaning and level.

JSON schema:
{
  "verdict": "clear" | "needs_revision",
  "summary": "one or two sentences",
  "taskCompletion": {"status": "strong" | "review" | "fix", "feedback": "..."},
  "grammarWordOrder": {"status": "strong" | "review" | "fix", "feedback": "..."},
  "vocabularyNaturalness": {"status": "strong" | "review" | "fix", "feedback": "..."},
  "charactersTyping": {"status": "strong" | "review" | "fix", "feedback": "..."},
  "placeholders": [{"english": "...", "chinese": "...", "pinyin": "...", "hskLevel": "HSK 1|HSK 2|HSK 3+|phrase", "note": "..."}],
  "correctedChinese": "...",
  "changes": [{"original": "...", "replacement": "...", "reason": "..."}],
  "revisionPrompt": "one specific thing to try in a revision"
}`;
}

function normalizeFeedback(value: unknown): Feedback | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const item = value as Record<string, unknown>;
  if (!isText(item.summary) || !isText(item.correctedChinese) || !isText(item.revisionPrompt)) {
    return null;
  }
  const section = (candidate: unknown) => {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
    const row = candidate as Record<string, unknown>;
    if (!isText(row.status) || !isText(row.feedback)) return null;
    return { status: row.status.slice(0, 24), feedback: row.feedback.slice(0, 1_000) };
  };
  const taskCompletion = section(item.taskCompletion);
  const grammarWordOrder = section(item.grammarWordOrder);
  const vocabularyNaturalness = section(item.vocabularyNaturalness);
  const charactersTyping = section(item.charactersTyping);
  if (!taskCompletion || !grammarWordOrder || !vocabularyNaturalness || !charactersTyping) return null;

  const placeholders = Array.isArray(item.placeholders)
    ? item.placeholders.slice(0, 20).flatMap((candidate) => {
        if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return [];
        const row = candidate as Record<string, unknown>;
        if (!isText(row.english) || !isText(row.chinese)) return [];
        return [{
          english: row.english.slice(0, 120),
          chinese: row.chinese.slice(0, 80),
          pinyin: isText(row.pinyin) ? row.pinyin.slice(0, 160) : "",
          hskLevel: isText(row.hskLevel) ? row.hskLevel.slice(0, 40) : "Not classified",
          note: isText(row.note) ? row.note.slice(0, 300) : "",
        }];
      })
    : [];
  const changes = Array.isArray(item.changes)
    ? item.changes.slice(0, 12).flatMap((candidate) => {
        if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return [];
        const row = candidate as Record<string, unknown>;
        if (!isText(row.original) || !isText(row.replacement) || !isText(row.reason)) return [];
        return [{
          original: row.original.slice(0, 200),
          replacement: row.replacement.slice(0, 200),
          reason: row.reason.slice(0, 500),
        }];
      })
    : [];

  return {
    verdict: item.verdict === "clear" ? "clear" : "needs_revision",
    summary: item.summary.slice(0, 1_000),
    taskCompletion,
    grammarWordOrder,
    vocabularyNaturalness,
    charactersTyping,
    placeholders,
    correctedChinese: item.correctedChinese.slice(0, 5_000),
    changes,
    revisionPrompt: item.revisionPrompt.slice(0, 1_000),
  };
}

function enrichPlaceholderLevels(feedback: Feedback) {
  for (const placeholder of feedback.placeholders) {
    const exact = content.words.find((word) => word.hanzi === placeholder.chinese);
    if (exact) placeholder.hskLevel = `HSK ${exact.hsk}`;
  }
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
