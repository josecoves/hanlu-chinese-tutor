import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

const VALID_MODES = new Set(["prompt", "message", "translation", "guided"]);

async function getDatabase() {
  const { env } = await import("cloudflare:workers");
  return env.DB;
}

function unauthorized() {
  return NextResponse.json(
    { error: "Sign in is required to save writing." },
    { status: 401 },
  );
}

export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return unauthorized();

  const db = await getDatabase();
  const rows = await db.prepare(
    `SELECT id, mode, hsk_level, prompt_text, response_text,
            target_words_json, feedback_json, created_at, updated_at
       FROM writing_attempts
      WHERE user_id = ?
      ORDER BY updated_at DESC
      LIMIT 30`,
  )
    .bind(user.id)
    .all();

  return NextResponse.json({ attempts: rows.results ?? [] });
}

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return unauthorized();

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid writing payload." }, { status: 400 });
  }

  const id = typeof body.id === "string" && /^[a-zA-Z0-9-]{8,80}$/.test(body.id)
    ? body.id
    : crypto.randomUUID();
  const mode = typeof body.mode === "string" ? body.mode : "";
  const hskLevel = Number(body.hskLevel);
  const promptText = typeof body.promptText === "string" ? body.promptText.trim() : "";
  const responseText = typeof body.responseText === "string" ? body.responseText.trim() : "";
  const targetWords = Array.isArray(body.targetWords)
    ? body.targetWords.filter((word): word is string => typeof word === "string").slice(0, 8)
    : [];

  if (
    !VALID_MODES.has(mode) ||
    ![1, 2].includes(hskLevel) ||
    !promptText ||
    promptText.length > 2_000 ||
    responseText.length > 5_000
  ) {
    return NextResponse.json({ error: "Invalid writing payload." }, { status: 400 });
  }

  const now = new Date().toISOString();
  const db = await getDatabase();
  await db.prepare(
    `INSERT INTO writing_attempts
       (id, user_id, mode, hsk_level, prompt_text, response_text,
        target_words_json, feedback_json, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
     ON CONFLICT(id) DO UPDATE SET
       mode = excluded.mode,
       hsk_level = excluded.hsk_level,
       prompt_text = excluded.prompt_text,
       response_text = excluded.response_text,
       target_words_json = excluded.target_words_json,
       updated_at = excluded.updated_at
     WHERE writing_attempts.user_id = excluded.user_id`,
  )
    .bind(
      id,
      user.id,
      mode,
      hskLevel,
      promptText,
      responseText,
      JSON.stringify(targetWords),
      now,
      now,
    )
    .run();

  return NextResponse.json({ ok: true, id, updatedAt: now });
}
