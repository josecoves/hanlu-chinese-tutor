import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

async function getProgressDatabase() {
  const { env } = await import("cloudflare:workers");
  return env.DB;
}

type StoredStoryProgress = {
  sentenceIndex: number;
  status?: "new" | "reading" | "finished";
  completedAt?: string;
  completedSentences?: number[];
  hardWords?: Record<string, number[]>;
};

type StoredVocabularyProgress = {
  listeningScore?: number;
  readingScore?: number;
  practices: number;
  lastReviewTs?: string;
  needsPractice?: boolean;
  known?: boolean;
};

type StoredProgress = {
  version: 2;
  declaredHskBand: number;
  stories: Record<string, StoredStoryProgress>;
  grammar: Record<string, "new" | "practicing" | "learned">;
  vocabulary: Record<string, StoredVocabularyProgress>;
};

const EMPTY_PROGRESS: StoredProgress = {
  version: 2,
  declaredHskBand: 0,
  stories: {},
  grammar: {},
  vocabulary: {},
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
  if (candidate.version === 1) return migrateVersionOne(candidate);
  if (candidate.version !== 2) return null;
  if (!isPlainRecord(candidate.stories) || !isPlainRecord(candidate.grammar)) return null;
  if (!isPlainRecord(candidate.vocabulary)) return null;

  const stories: StoredProgress["stories"] = {};
  for (const [id, entry] of Object.entries(candidate.stories)) {
    if (!isPlainRecord(entry) || !isValidId(id)) return null;
    const sentenceIndex = entry.sentenceIndex;
    if (!Number.isInteger(sentenceIndex) || Number(sentenceIndex) < 0 || Number(sentenceIndex) > 1_000) {
      return null;
    }
    if (entry.completedAt !== undefined && typeof entry.completedAt !== "string") return null;
    const completedSentences = Array.isArray(entry.completedSentences)
      ? entry.completedSentences
          .filter((item): item is number => Number.isInteger(item) && Number(item) >= 0 && Number(item) <= 1_000)
          .slice(0, 1_000)
      : [];
    const hardWords: Record<string, number[]> = {};
    if (isPlainRecord(entry.hardWords)) {
      for (const [sentence, ids] of Object.entries(entry.hardWords)) {
        if (!/^\d{1,4}$/.test(sentence) || !Array.isArray(ids)) continue;
        hardWords[sentence] = ids
          .filter((item): item is number => Number.isInteger(item) && Number(item) > 0)
          .slice(0, 500);
      }
    }
    const status = ["new", "reading", "finished"].includes(String(entry.status))
      ? entry.status as StoredStoryProgress["status"]
      : undefined;
    stories[id] = {
      sentenceIndex: sentenceIndex as number,
      ...(status ? { status } : {}),
      ...(typeof entry.completedAt === "string" ? { completedAt: entry.completedAt } : {}),
      ...(completedSentences.length ? { completedSentences } : {}),
      ...(Object.keys(hardWords).length ? { hardWords } : {}),
    };
  }

  const grammar: StoredProgress["grammar"] = {};
  for (const [id, status] of Object.entries(candidate.grammar)) {
    if (!isValidId(id) || !["new", "practicing", "learned"].includes(String(status))) {
      return null;
    }
    grammar[id] = status as StoredProgress["grammar"][string];
  }

  const vocabulary: StoredProgress["vocabulary"] = {};
  for (const [id, entry] of Object.entries(candidate.vocabulary)) {
    if (!isValidId(id) || !isPlainRecord(entry)) return null;
    const practices = Number(entry.practices ?? 0);
    if (!Number.isInteger(practices) || practices < 0 || practices > 1_000_000) return null;
    const listeningScore = validScore(entry.listeningScore);
    const readingScore = validScore(entry.readingScore);
    vocabulary[id] = {
      practices,
      ...(listeningScore !== undefined ? { listeningScore } : {}),
      ...(readingScore !== undefined ? { readingScore } : {}),
      ...(typeof entry.lastReviewTs === "string" ? { lastReviewTs: entry.lastReviewTs } : {}),
      ...(entry.needsPractice === true ? { needsPractice: true } : {}),
      ...(typeof entry.known === "boolean" ? { known: entry.known } : {}),
    };
  }

  return {
    version: 2,
    declaredHskBand: [0, 1, 2, 3].includes(Number(candidate.declaredHskBand))
      ? Number(candidate.declaredHskBand)
      : 0,
    stories,
    grammar,
    vocabulary,
  };
}

function migrateVersionOne(candidate: Record<string, unknown>): StoredProgress | null {
  if (!isPlainRecord(candidate.stories) || !isPlainRecord(candidate.grammar)) return null;
  return normalizeProgress({
    version: 2,
    declaredHskBand: 0,
    stories: candidate.stories,
    grammar: candidate.grammar,
    vocabulary: {},
  });
}

function validScore(value: unknown) {
  const score = Number(value);
  return Number.isFinite(score) && score >= 0 && score <= 100
    ? Math.round(score)
    : undefined;
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
  if (serialized.length > 350_000) {
    return NextResponse.json({ error: "Progress payload is too large." }, { status: 413 });
  }

  const db = await getProgressDatabase();
  await db.prepare(
    `INSERT INTO learner_progress (user_id, schema_version, progress_json, updated_at)
     VALUES (?, 2, ?, ?)
     ON CONFLICT(user_id) DO UPDATE SET
       schema_version = excluded.schema_version,
       progress_json = excluded.progress_json,
       updated_at = excluded.updated_at`,
  )
    .bind(user.id, serialized, new Date().toISOString())
    .run();

  return NextResponse.json({ ok: true });
}
