import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../chatgpt-auth";
import { EMPTY_PROGRESS, mergeProgress, normalizeProgress } from "./model";

export const dynamic = "force-dynamic";

async function database() {
  const { env } = await import("cloudflare:workers");
  return env.DB;
}

function unauthorized() {
  return NextResponse.json({ error: "Sign in is required to sync progress." }, { status: 401 });
}

export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return unauthorized();
  const db = await database();
  const row = await db.prepare("SELECT progress_json FROM learner_progress WHERE user_id = ?")
    .bind(user.id).first<{ progress_json: string }>();
  if (!row) return NextResponse.json({ progress: EMPTY_PROGRESS });
  try {
    return NextResponse.json({ progress: normalizeProgress(JSON.parse(row.progress_json)) ?? EMPTY_PROGRESS });
  } catch {
    return NextResponse.json({ progress: EMPTY_PROGRESS });
  }
}

export async function PUT(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return unauthorized();
  let incoming = null;
  try { incoming = normalizeProgress(await request.json()); } catch { /* handled below */ }
  if (!incoming) return NextResponse.json({ error: "Invalid progress payload." }, { status: 400 });

  const db = await database();
  const row = await db.prepare("SELECT progress_json FROM learner_progress WHERE user_id = ?")
    .bind(user.id).first<{ progress_json: string }>();
  let current = EMPTY_PROGRESS;
  try { current = row ? normalizeProgress(JSON.parse(row.progress_json)) ?? EMPTY_PROGRESS : EMPTY_PROGRESS; }
  catch { current = EMPTY_PROGRESS; }
  const progress = mergeProgress(current, incoming);
  const serialized = JSON.stringify(progress);
  if (serialized.length > 350_000) return NextResponse.json({ error: "Progress payload is too large." }, { status: 413 });
  await db.prepare(
    `INSERT INTO learner_progress (user_id, schema_version, progress_json, updated_at)
     VALUES (?, 2, ?, ?) ON CONFLICT(user_id) DO UPDATE SET
       schema_version=excluded.schema_version,progress_json=excluded.progress_json,updated_at=excluded.updated_at`,
  ).bind(user.id, serialized, new Date().toISOString()).run();
  return NextResponse.json({ ok: true, progress });
}
