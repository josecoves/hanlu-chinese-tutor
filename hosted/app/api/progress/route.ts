import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

async function getProgressDatabase() {
  const { env } = await import("cloudflare:workers");
  return env.DB;
}

type StoredStoryProgress = {
  sentenceIndex: number;
  completedAt?: string;
};

type StoredProgress = {
  version: 1;
  stories: Record<string, StoredStoryProgress>;
  grammar: Record<string, "new" | "practicing" | "learned">;
};

const EMPTY_PROGRESS: StoredProgress = {
  version: 1,
  stories: {},
  grammar: {},
};

function unauthorized() {
  return NextResponse.json(
    { error: "Sign in is required to sync progress." },
    { status: 401 },
  );
}

function normalizeProgress(value: unknown): StoredProgress | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const candidate = value as Record<string, unknown>;
  if (candidate.version !== 1) return null;
  if (!isPlainRecord(candidate.stories) || !isPlainRecord(candidate.grammar)) return null;

  const stories: StoredProgress["stories"] = {};
  for (const [id, entry] of Object.entries(candidate.stories)) {
    if (!isPlainRecord(entry) || !isValidId(id)) return null;
    const sentenceIndex = entry.sentenceIndex;
    if (!Number.isInteger(sentenceIndex) || sentenceIndex < 0 || sentenceIndex > 1_000) {
      return null;
    }
    if (entry.completedAt !== undefined && typeof entry.completedAt !== "string") return null;
    stories[id] = {
      sentenceIndex: sentenceIndex as number,
      ...(typeof entry.completedAt === "string" ? { completedAt: entry.completedAt } : {}),
    };
  }

  const grammar: StoredProgress["grammar"] = {};
  for (const [id, status] of Object.entries(candidate.grammar)) {
    if (!isValidId(id) || !["new", "practicing", "learned"].includes(String(status))) {
      return null;
    }
    grammar[id] = status as StoredProgress["grammar"][string];
  }

  return {
    version: 1,
    stories,
    grammar,
  };
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isValidId(value: string) {
  return /^\d{1,8}$/.test(value);
}

export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return unauthorized();

  const db = await getProgressDatabase();
  const row = await db.prepare(
    "SELECT progress_json FROM learner_progress WHERE user_id = ?",
  )
    .bind(user.id)
    .first<{ progress_json: string }>();

  if (!row) return NextResponse.json({ progress: EMPTY_PROGRESS });

  try {
    const progress = normalizeProgress(JSON.parse(row.progress_json));
    return NextResponse.json({ progress: progress ?? EMPTY_PROGRESS });
  } catch {
    return NextResponse.json({ progress: EMPTY_PROGRESS });
  }
}

export async function PUT(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return unauthorized();

  let progress: StoredProgress | null = null;
  try {
    progress = normalizeProgress(await request.json());
  } catch {
    // The response below deliberately does not echo the submitted content.
  }
  if (!progress) {
    return NextResponse.json({ error: "Invalid progress payload." }, { status: 400 });
  }

  const serialized = JSON.stringify(progress);
  if (serialized.length > 50_000) {
    return NextResponse.json({ error: "Progress payload is too large." }, { status: 413 });
  }

  const db = await getProgressDatabase();
  await db.prepare(
    `INSERT INTO learner_progress (user_id, schema_version, progress_json, updated_at)
     VALUES (?, 1, ?, ?)
     ON CONFLICT(user_id) DO UPDATE SET
       schema_version = excluded.schema_version,
       progress_json = excluded.progress_json,
       updated_at = excluded.updated_at`,
  )
    .bind(user.id, serialized, new Date().toISOString())
    .run();

  return NextResponse.json({ ok: true });
}
