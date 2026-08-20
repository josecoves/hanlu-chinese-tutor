import { NextResponse } from "next/server";
import { getProgressUser } from "../sync-auth";
import { EMPTY_PROGRESS, normalizeProgress } from "../progress/model";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const user = await getProgressUser(request);
  if (!user) return NextResponse.json({ error: "Private sync credentials are required." }, { status: 401 });
  const { env } = await import("cloudflare:workers");
  const [progressRow, readingRows] = await Promise.all([
    env.DB.prepare("SELECT progress_json,updated_at FROM learner_progress WHERE user_id=?")
      .bind(user.id).first<{ progress_json: string; updated_at: string }>(),
    env.DB.prepare(
      `SELECT id,provider,hsk_level,title,url,status,hard_words,notes,opened_at,
              completed_at,created_at,updated_at FROM external_readings
         WHERE user_id=? ORDER BY updated_at`,
    ).bind(user.id).all(),
  ]);
  let progress = EMPTY_PROGRESS;
  try {
    progress = progressRow ? normalizeProgress(JSON.parse(progressRow.progress_json)) ?? EMPTY_PROGRESS : EMPTY_PROGRESS;
  } catch { progress = EMPTY_PROGRESS; }
  return NextResponse.json({
    version: 1,
    serverTime: new Date().toISOString(),
    progressUpdatedAt: progressRow?.updated_at ?? null,
    progress,
    externalReadings: readingRows.results ?? [],
  });
}
