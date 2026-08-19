import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../../chatgpt-auth";

export const dynamic = "force-dynamic";

const DAILY_REQUEST_LIMIT = 35;
const DAILY_BUDGET_MICRO_USD = 20_000;
const REQUEST_RESERVATION_MICRO_USD = 500;
const MINUTE_REQUEST_LIMIT = 4;

type RuntimeEnv = {
  DB: {
    prepare(query: string): { bind(...values: unknown[]): { first<T>(): Promise<T | null>; run(): Promise<unknown> } };
  };
  DEEPSEEK_API_KEY?: string;
  DEEPSEEK_MODEL?: string;
};

type GrammarFeedback = {
  verdict: "correct" | "needs_revision";
  targetGrammarCorrect: boolean;
  summary: string;
  explanation: string;
  correctedAnswer: string;
  vocabularyHelp: Array<{ english: string; chinese: string; pinyin: string; hskLevel: string }>;
  differences: Array<{ learner: string; suggested: string; reason: string }>;
};

function error(message: string, status: number) { return NextResponse.json({ error: message }, { status }); }

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return error("Sign in is required to ask the tutor.", 401);
  let body: Record<string, unknown>;
  try { body = await request.json() as Record<string, unknown>; }
  catch { return error("The review request could not be read.", 400); }
  const attemptId = typeof body.attemptId === "string" && /^[a-zA-Z0-9-]{8,80}$/.test(body.attemptId) ? body.attemptId : crypto.randomUUID();
  const lesson = typeof body.lesson === "string" ? body.lesson.trim().slice(0, 300) : "";
  const pattern = typeof body.pattern === "string" ? body.pattern.trim().slice(0, 500) : "";
  const prompt = typeof body.prompt === "string" ? body.prompt.trim().slice(0, 2_000) : "";
  const answer = typeof body.answer === "string" ? body.answer.trim().slice(0, 4_000) : "";
  const expected = typeof body.expected === "string" ? body.expected.trim().slice(0, 4_000) : "";
  const question = typeof body.question === "string" ? body.question.trim().slice(0, 1_500) : "";
  if (!lesson || !pattern || !prompt || !answer || !expected) return error("Complete the exercise before asking the tutor.", 400);

  const { env } = await import("cloudflare:workers");
  const runtime = env as unknown as RuntimeEnv;
  if (!runtime.DEEPSEEK_API_KEY) return error("AI review is not configured yet. Your attempt is still saved.", 503);
  const now = new Date();
  const nowIso = now.toISOString();
  const date = nowIso.slice(0, 10);
  const usage = await runtime.DB.prepare(
    "SELECT COUNT(*) AS requests,COALESCE(SUM(reserved_micro_usd),0) AS reserved FROM writing_ai_usage WHERE usage_date=?",
  ).bind(date).first<{requests:number;reserved:number}>();
  const recent = await runtime.DB.prepare(
    "SELECT COUNT(*) AS requests FROM writing_ai_usage WHERE user_id=? AND created_at>=?",
  ).bind(user.id,new Date(now.getTime()-60_000).toISOString()).first<{requests:number}>();
  if (Number(recent?.requests ?? 0) >= MINUTE_REQUEST_LIMIT) return error("Please wait a minute before asking again.", 429);
  if (Number(usage?.requests ?? 0) >= DAILY_REQUEST_LIMIT || Number(usage?.reserved ?? 0)+REQUEST_RESERVATION_MICRO_USD > DAILY_BUDGET_MICRO_USD) {
    return error("Hanlu's daily AI allowance has been reached. Try again tomorrow.", 429);
  }
  const reservationId = crypto.randomUUID();
  await runtime.DB.prepare(
    "INSERT INTO writing_ai_usage (id,user_id,usage_date,reserved_micro_usd,status,created_at) VALUES (?,?,?,?,?,?)",
  ).bind(reservationId,user.id,date,REQUEST_RESERVATION_MICRO_USD,"reserved",nowIso).run();

  try {
    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: { authorization: `Bearer ${runtime.DEEPSEEK_API_KEY}`, "content-type": "application/json" },
      body: JSON.stringify({
        model: runtime.DEEPSEEK_MODEL || "deepseek-chat",
        response_format: { type: "json_object" },
        temperature: 0.15,
        max_tokens: 900,
        messages: [
          { role: "system", content: `You are Hanlu's careful Mandarin grammar tutor. Judge the target grammar separately from vocabulary, characters, punctuation, and style. Accept natural alternative answers, omitted subjects/objects when context allows, formal/informal synonyms, simplified/traditional forms, and reasonable English placeholders for unknown vocabulary. Do not require the model wording. Explain the single most useful distinction without repeating yourself. Return only JSON: {"verdict":"correct|needs_revision","targetGrammarCorrect":true,"summary":"...","explanation":"...","correctedAnswer":"...","vocabularyHelp":[{"english":"...","chinese":"...","pinyin":"...","hskLevel":"HSK 1|HSK 2|HSK 3+|phrase"}],"differences":[{"learner":"...","suggested":"...","reason":"..."}]}.` },
          { role: "user", content: JSON.stringify({ lesson, target_pattern: pattern, exercise: prompt, learner_answer: answer, model_answer: expected, follow_up_question: question || null }) },
        ],
      }),
    });
    if (!response.ok) throw new Error("provider");
    const payload = await response.json() as { choices?: Array<{message?:{content?:string}}> };
    const raw = payload.choices?.[0]?.message?.content;
    if (!raw) throw new Error("empty");
    const feedback = normalize(JSON.parse(raw));
    if (!feedback) throw new Error("invalid");
    await runtime.DB.prepare("UPDATE writing_ai_usage SET status='completed' WHERE id=?").bind(reservationId).run();
    await runtime.DB.prepare(
      `UPDATE grammar_attempts SET verdict=?,feedback_json=?,updated_at=? WHERE id=? AND user_id=?`,
    ).bind(feedback.verdict,JSON.stringify(feedback),nowIso,attemptId,user.id).run();
    return NextResponse.json({ attemptId, feedback });
  } catch {
    await runtime.DB.prepare("UPDATE writing_ai_usage SET status='failed' WHERE id=?").bind(reservationId).run();
    return error("The AI tutor could not finish. Your attempt is still saved.", 502);
  }
}

function normalize(value: unknown): GrammarFeedback | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const item = value as Record<string, unknown>;
  const verdict = item.verdict === "correct" ? "correct" : item.verdict === "needs_revision" ? "needs_revision" : null;
  if (!verdict || typeof item.summary !== "string" || typeof item.explanation !== "string" || typeof item.correctedAnswer !== "string") return null;
  const vocabularyHelp = Array.isArray(item.vocabularyHelp) ? item.vocabularyHelp.slice(0,12).flatMap((row) => {
    if (!row || typeof row !== "object") return [];
    const r = row as Record<string, unknown>;
    if (typeof r.english !== "string" || typeof r.chinese !== "string") return [];
    return [{ english:r.english.slice(0,100),chinese:r.chinese.slice(0,80),pinyin:String(r.pinyin??"").slice(0,120),hskLevel:String(r.hskLevel??"phrase").slice(0,20) }];
  }) : [];
  const differences = Array.isArray(item.differences) ? item.differences.slice(0,8).flatMap((row) => {
    if (!row || typeof row !== "object") return [];
    const r = row as Record<string, unknown>;
    if (typeof r.reason !== "string") return [];
    return [{ learner:String(r.learner??"").slice(0,200),suggested:String(r.suggested??"").slice(0,200),reason:r.reason.slice(0,700) }];
  }) : [];
  return { verdict, targetGrammarCorrect: item.targetGrammarCorrect === true, summary:item.summary.slice(0,700), explanation:item.explanation.slice(0,1800), correctedAnswer:item.correctedAnswer.slice(0,1000), vocabularyHelp, differences };
}
