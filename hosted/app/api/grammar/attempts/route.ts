import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../../chatgpt-auth";

export const dynamic = "force-dynamic";

export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return NextResponse.json({ error: "Sign in is required." }, { status: 401 });
  const { env } = await import("cloudflare:workers");
  const rows = await env.DB.prepare(
    `SELECT id,grammar_id,direction,prompt_text,response_text,expected_text,verdict,feedback_json,created_at,updated_at
       FROM grammar_attempts WHERE user_id=? ORDER BY updated_at DESC LIMIT 60`,
  ).bind(user.id).all();
  return NextResponse.json({ attempts: rows.results ?? [] });
}

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return NextResponse.json({ error: "Sign in is required." }, { status: 401 });
  let body: Record<string, unknown>;
  try { body = await request.json() as Record<string, unknown>; }
  catch { return NextResponse.json({ error: "Invalid attempt." }, { status: 400 }); }
  const id = typeof body.id === "string" && /^[a-zA-Z0-9-]{8,80}$/.test(body.id) ? body.id : crypto.randomUUID();
  const grammarId = Number(body.grammarId);
  const direction = body.direction === "zh_en" ? "zh_en" : body.direction === "en_zh" ? "en_zh" : "";
  const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
  const response = typeof body.response === "string" ? body.response.trim() : "";
  const expected = typeof body.expected === "string" ? body.expected.trim() : "";
  const verdict = ["correct", "pending", "needs_revision"].includes(String(body.verdict)) ? String(body.verdict) : "pending";
  if (!Number.isInteger(grammarId) || grammarId < 1 || !direction || !prompt || !response || !expected || prompt.length > 2_000 || response.length > 4_000) {
    return NextResponse.json({ error: "Invalid attempt." }, { status: 400 });
  }
  const now = new Date().toISOString();
  const { env } = await import("cloudflare:workers");
  await env.DB.prepare(
    `INSERT INTO grammar_attempts
       (id,user_id,grammar_id,direction,prompt_text,response_text,expected_text,verdict,feedback_json,created_at,updated_at)
     VALUES (?,?,?,?,?,?,?,?,NULL,?,?)
     ON CONFLICT(id) DO UPDATE SET response_text=excluded.response_text,verdict=excluded.verdict,updated_at=excluded.updated_at
     WHERE grammar_attempts.user_id=excluded.user_id`,
  ).bind(id,user.id,grammarId,direction,prompt,response,expected,verdict,now,now).run();
  return NextResponse.json({ ok: true, id });
}
