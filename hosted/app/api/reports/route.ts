import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return NextResponse.json({ error: "Sign in is required to flag a problem." }, { status: 401 });
  let body: Record<string, unknown>;
  try { body = await request.json() as Record<string, unknown>; }
  catch { return NextResponse.json({ error: "Invalid report." }, { status: 400 }); }
  const kind = typeof body.kind === "string" ? body.kind.slice(0, 40) : "learning";
  const referenceId = typeof body.referenceId === "string" ? body.referenceId.slice(0, 100) : "unknown";
  const note = typeof body.note === "string" ? body.note.trim().slice(0, 3_000) : "Flagged while studying";
  const context = body.context && typeof body.context === "object" ? JSON.stringify(body.context).slice(0, 20_000) : "{}";
  const { env } = await import("cloudflare:workers");
  const id = crypto.randomUUID();
  await env.DB.prepare(
    `INSERT INTO learning_reports (id,user_id,kind,reference_id,note,context_json,status,created_at)
     VALUES (?,?,?,?,?,?,'open',?)`,
  ).bind(id,user.id,kind,referenceId,note,context,new Date().toISOString()).run();
  return NextResponse.json({ ok: true, id });
}
