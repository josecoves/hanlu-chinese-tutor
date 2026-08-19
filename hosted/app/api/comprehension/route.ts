import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

const PROVIDERS = new Set(["mandarinbean", "hskreading"]);
const STATUSES = new Set(["new", "in_progress", "completed"]);

async function database() {
  const { env } = await import("cloudflare:workers");
  return env.DB;
}

function error(message: string, status: number) {
  return NextResponse.json({ error: message }, { status });
}

export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return error("Sign in is required to load saved readers.", 401);
  const db = await database();
  const rows = await db.prepare(
    `SELECT id, provider, hsk_level, title, url, status, hard_words, notes,
            opened_at, completed_at, created_at, updated_at
       FROM external_readings WHERE user_id = ? ORDER BY updated_at DESC`,
  ).bind(user.id).all();
  return NextResponse.json({ readings: rows.results ?? [] });
}

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return error("Sign in is required to save a reader.", 401);
  let body: Record<string, unknown>;
  try { body = await request.json() as Record<string, unknown>; }
  catch { return error("The reader could not be read.", 400); }

  const rawUrl = typeof body.url === "string" ? body.url.trim() : "";
  let parsed: URL;
  try { parsed = new URL(rawUrl); }
  catch { return error("Enter a complete reader URL.", 400); }
  if (parsed.protocol !== "https:") return error("Reader links must use HTTPS.", 400);

  const inferred = parsed.hostname.includes("mandarinbean.com")
    ? "mandarinbean"
    : parsed.hostname.includes("hskreading.com") ? "hskreading" : "";
  const provider = inferred || (typeof body.provider === "string" ? body.provider : "");
  const hskLevel = Number(body.hskLevel);
  const status = typeof body.status === "string" ? body.status : "completed";
  if (!PROVIDERS.has(provider) || !Number.isInteger(hskLevel) || hskLevel < 1 || hskLevel > 6 || !STATUSES.has(status)) {
    return error("Choose a supported source, HSK level, and status.", 400);
  }
  const fallbackTitle = decodeURIComponent(parsed.pathname.split("/").filter(Boolean).at(-1) || "Saved reader")
    .replace(/[-_]+/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
  const title = (typeof body.title === "string" ? body.title.trim() : "") || fallbackTitle;
  const hardWords = typeof body.hardWords === "string" ? body.hardWords.trim().slice(0, 2_000) : "";
  const notes = typeof body.notes === "string" ? body.notes.trim().slice(0, 8_000) : "";
  if (title.length > 200 || rawUrl.length > 1_000) return error("The reader details are too long.", 413);
  const id = typeof body.id === "string" && /^[a-zA-Z0-9-]{8,80}$/.test(body.id) ? body.id : crypto.randomUUID();
  const now = new Date().toISOString();
  const openedAt = status === "in_progress" || status === "completed" ? now : null;
  const completedAt = status === "completed" ? now : null;
  const db = await database();
  await db.prepare(
    `INSERT INTO external_readings
       (id,user_id,provider,hsk_level,title,url,status,hard_words,notes,opened_at,completed_at,created_at,updated_at)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
     ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,hsk_level=excluded.hsk_level,
       title=excluded.title,url=excluded.url,status=excluded.status,hard_words=excluded.hard_words,
       notes=excluded.notes,opened_at=COALESCE(external_readings.opened_at,excluded.opened_at),
       completed_at=excluded.completed_at,updated_at=excluded.updated_at
     WHERE external_readings.user_id=excluded.user_id`,
  ).bind(id,user.id,provider,hskLevel,title,rawUrl,status,hardWords,notes,openedAt,completedAt,now,now).run();
  return NextResponse.json({ ok: true, id, provider, updatedAt: now });
}

export async function PATCH(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return error("Sign in is required to update a reader.", 401);
  let body: Record<string, unknown>;
  try { body = await request.json() as Record<string, unknown>; }
  catch { return error("The update could not be read.", 400); }
  const id = typeof body.id === "string" ? body.id : "";
  const status = typeof body.status === "string" ? body.status : "";
  if (!/^[a-zA-Z0-9-]{8,80}$/.test(id) || !STATUSES.has(status)) return error("Invalid reader update.", 400);
  const now = new Date().toISOString();
  const db = await database();
  await db.prepare(
    `UPDATE external_readings SET status=?, opened_at=CASE WHEN ?!='new' THEN COALESCE(opened_at,?) ELSE opened_at END,
       completed_at=CASE WHEN ?='completed' THEN ? ELSE NULL END, updated_at=? WHERE id=? AND user_id=?`,
  ).bind(status,status,now,status,now,now,id,user.id).run();
  return NextResponse.json({ ok: true });
}
