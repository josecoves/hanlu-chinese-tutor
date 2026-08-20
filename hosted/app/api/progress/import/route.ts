import { NextResponse } from "next/server";
import content from "../../../hanlu-data.json";
import { getProgressUser } from "../../sync-auth";
import { EMPTY_PROGRESS, mergeProgress, normalizeProgress } from "../model";

export const dynamic = "force-dynamic";

type RecordValue = Record<string, unknown>;
type VocabularySummary = {
  listeningScore?: number;
  readingScore?: number;
  practices: number;
  lastReviewTs?: string;
  needsPractice?: boolean;
  known?: boolean;
  updatedAt?: string;
};

function record(value: unknown): value is RecordValue {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function rows(value: unknown): RecordValue[] {
  return Array.isArray(value) ? value.filter(record) : [];
}

export async function POST(request: Request) {
  const user = await getProgressUser(request);
  if (!user) {
    return NextResponse.json({ error: "Sign in is required to import progress." }, { status: 401 });
  }

  let payload: RecordValue;
  let serialized: string;
  try {
    payload = await request.json() as RecordValue;
    serialized = JSON.stringify(payload);
  } catch {
    return NextResponse.json({ error: "Choose a valid Hanlu progress JSON export." }, { status: 400 });
  }
  const schemaVersion = Number(payload.schema);
  if (!Number.isInteger(schemaVersion) || schemaVersion < 1 || schemaVersion > 20) {
    return NextResponse.json({ error: "This is not a recognized Hanlu progress export." }, { status: 400 });
  }
  if (serialized.length > 2_000_000) {
    return NextResponse.json({ error: "The progress export is unexpectedly large." }, { status: 413 });
  }

  const wordByHeadword = new Map(content.words.map((word) => [word.hanzi, word]));
  const storyByTitle = new Map(content.stories.map((story) => [story.titleZh, story]));
  const grammarByTitle = new Map(content.grammar.map((lesson) => [`${lesson.level}:${lesson.titleEn}`, lesson]));
  const declaredHskBand = [0, 1, 2, 3].includes(Number(payload.declared_hsk_band))
    ? Number(payload.declared_hsk_band)
    : 0;

  const vocabulary: Record<string, VocabularySummary> = {};
  for (const state of rows(payload.memory_state)) {
    const word = wordByHeadword.get(String(state.headword ?? ""));
    if (!word) continue;
    const id = String(word.id);
    const summary = vocabulary[id] ?? { practices: 0 };
    const score = retrievabilityScore(state);
    if (state.facet === "listening" && score !== undefined) summary.listeningScore = score;
    if (state.facet === "reading-recognition" && score !== undefined) summary.readingScore = score;
    if (typeof state.last_review_ts === "string" && (!summary.updatedAt || state.last_review_ts > summary.updatedAt)) {
      summary.updatedAt = state.last_review_ts;
    }
    vocabulary[id] = summary;
  }

  const latestGrade = new Map<string, { grade: number; ts: string }>();
  for (const review of rows(payload.review_log)) {
    const word = wordByHeadword.get(String(review.headword ?? ""));
    if (!word) continue;
    const id = String(word.id);
    const summary = vocabulary[id] ?? { practices: 0 };
    summary.practices += 1;
    const ts = String(review.ts ?? "");
    if (!summary.lastReviewTs || ts > summary.lastReviewTs) summary.lastReviewTs = ts;
    if (!summary.updatedAt || ts > summary.updatedAt) summary.updatedAt = ts;
    const current = latestGrade.get(id);
    if (!current || ts > current.ts) latestGrade.set(id, { grade: Number(review.grade), ts });
    vocabulary[id] = summary;
  }

  for (const word of content.words) {
    const id = String(word.id);
    const summary = vocabulary[id] ?? { practices: 0 };
    const latest = latestGrade.get(id);
    if (latest) summary.known = latest.grade > 1;
    else if (declaredHskBand && word.hsk <= declaredHskBand) summary.known = true;
    if (summary.known || summary.practices || summary.listeningScore !== undefined || summary.readingScore !== undefined) {
      vocabulary[id] = summary;
    }
  }
  for (const override of rows(payload.item_knowledge_override)) {
    const word = wordByHeadword.get(String(override.headword ?? ""));
    if (!word || override.status !== "needs_practice") continue;
    const id = String(word.id);
    const updatedAt = typeof override.updated_ts === "string" ? override.updated_ts : undefined;
    vocabulary[id] = { ...(vocabulary[id] ?? { practices: 0 }), needsPractice: true, known: false, ...(updatedAt ? { updatedAt } : {}) };
  }
  for (const cloudState of rows(payload.cloud_vocabulary_progress)) {
    const word = wordByHeadword.get(String(cloudState.headword ?? ""));
    if (!word) continue;
    const id = String(word.id);
    const current = vocabulary[id] ?? { practices: 0 };
    const updatedAt = typeof cloudState.updated_ts === "string" ? cloudState.updated_ts : "";
    if (updatedAt && updatedAt < String(current.updatedAt ?? current.lastReviewTs ?? "")) continue;
    vocabulary[id] = {
      practices: Math.max(current.practices, boundedInteger(cloudState.practices, 0, 1_000_000)),
      ...(validScore(cloudState.listening_score) ?? current.listeningScore) !== undefined
        ? { listeningScore: validScore(cloudState.listening_score) ?? current.listeningScore } : {},
      ...(validScore(cloudState.reading_score) ?? current.readingScore) !== undefined
        ? { readingScore: validScore(cloudState.reading_score) ?? current.readingScore } : {},
      ...((typeof cloudState.last_review_ts === "string" ? cloudState.last_review_ts : current.lastReviewTs)
        ? { lastReviewTs: typeof cloudState.last_review_ts === "string" ? cloudState.last_review_ts : current.lastReviewTs } : {}),
      ...(typeof cloudState.needs_practice === "number" || typeof cloudState.needs_practice === "boolean"
        ? { needsPractice: Boolean(cloudState.needs_practice) } : {}),
      ...(typeof cloudState.known === "number" || typeof cloudState.known === "boolean"
        ? { known: Boolean(cloudState.known) } : {}),
      ...(updatedAt ? { updatedAt } : {}),
    };
  }

  const stories: Record<string, RecordValue> = {};
  for (const state of rows(payload.story_state)) {
    const story = storyByTitle.get(String(state.title_zh ?? ""));
    if (!story) continue;
    stories[String(story.id)] = {
      sentenceIndex: boundedInteger(state.current_index, 0, Math.max(0, story.sentences.length - 1)),
      status: ["new", "reading", "finished"].includes(String(state.status)) ? state.status : "new",
      ...(state.status === "finished" ? { completedAt: String(state.updated_ts ?? new Date().toISOString()) } : {}),
      ...(typeof state.updated_ts === "string" ? { updatedAt: state.updated_ts } : {}),
      completedSentences: [],
      hardWords: {},
    };
  }
  for (const sentence of rows(payload.story_sentence_progress)) {
    const story = storyByTitle.get(String(sentence.title_zh ?? ""));
    if (!story) continue;
    const id = String(story.id);
    const state = stories[id] ?? { sentenceIndex: 0, status: "reading", completedSentences: [], hardWords: {} };
    const completed = Array.isArray(state.completedSentences) ? state.completedSentences as number[] : [];
    const index = boundedInteger(sentence.sentence_index, 0, Math.max(0, story.sentences.length - 1));
    if (!completed.includes(index)) completed.push(index);
    state.completedSentences = completed.sort((a, b) => a - b);
    if (typeof sentence.completed_ts === "string" && sentence.completed_ts > String(state.updatedAt ?? "")) state.updatedAt = sentence.completed_ts;
    stories[id] = state;
  }
  for (const exposure of rows(payload.story_word_exposure)) {
    if (exposure.status !== "hard") continue;
    const story = storyByTitle.get(String(exposure.title_zh ?? ""));
    const word = wordByHeadword.get(String(exposure.headword ?? ""));
    if (!story || !word) continue;
    const id = String(story.id);
    const state = stories[id] ?? { sentenceIndex: 0, status: "reading", completedSentences: [], hardWords: {} };
    const hardWords = record(state.hardWords) ? state.hardWords as Record<string, number[]> : {};
    const sentence = String(boundedInteger(exposure.sentence_index, 0, Math.max(0, story.sentences.length - 1)));
    const ids = Array.isArray(hardWords[sentence]) ? hardWords[sentence] : [];
    if (!ids.includes(word.id)) ids.push(word.id);
    hardWords[sentence] = ids;
    state.hardWords = hardWords;
    if (typeof exposure.updated_ts === "string" && exposure.updated_ts > String(state.updatedAt ?? "")) state.updatedAt = exposure.updated_ts;
    stories[id] = state;
  }

  const grammar: Record<string, "new" | "practicing" | "learned"> = {};
  const grammarUpdatedAt: Record<string, string> = {};
  for (const state of rows(payload.grammar_state)) {
    const lesson = grammarByTitle.get(`${Number(state.level)}:${String(state.title_en ?? "")}`);
    if (!lesson) continue;
    const status = String(state.status);
    grammar[String(lesson.id)] = status === "learned" ? "learned" : status === "practicing" ? "practicing" : "new";
    if (typeof state.updated_ts === "string") grammarUpdatedAt[String(lesson.id)] = state.updated_ts;
  }
  for (const attempt of rows(payload.grammar_attempt)) {
    const lesson = grammarByTitle.get(`${Number(attempt.level)}:${String(attempt.title_en ?? "")}`);
    if (lesson && !grammar[String(lesson.id)]) grammar[String(lesson.id)] = "practicing";
    if (lesson && typeof attempt.ts === "string" && attempt.ts > String(grammarUpdatedAt[String(lesson.id)] ?? "")) {
      grammarUpdatedAt[String(lesson.id)] = attempt.ts;
    }
  }

  const now = new Date().toISOString();
  const { env } = await import("cloudflare:workers");
  const incoming = normalizeProgress({ version: 2, declaredHskBand, stories, grammar, grammarUpdatedAt, vocabulary });
  if (!incoming) return NextResponse.json({ error: "The imported progress could not be normalized." }, { status: 400 });
  const existingRow = await env.DB.prepare("SELECT progress_json FROM learner_progress WHERE user_id=?")
    .bind(user.id).first<{ progress_json: string }>();
  let existing = EMPTY_PROGRESS;
  try { existing = existingRow ? normalizeProgress(JSON.parse(existingRow.progress_json)) ?? EMPTY_PROGRESS : EMPTY_PROGRESS; }
  catch { existing = EMPTY_PROGRESS; }
  const progress = mergeProgress(existing, incoming);
  const externalStatements = rows(payload.external_resource_progress).flatMap((resource) => {
    const resourceId = String(resource.resource_id ?? "");
    if (!resourceId.startsWith("reading:")) return [];
    const provider = String(resource.provider ?? "").toLowerCase().includes("mandarin") ? "mandarinbean" : "hskreading";
    const levelMatch = String(resource.level ?? "").match(/\d/);
    const hskLevel = levelMatch ? Number(levelMatch[0]) : 1;
    const url = String(resource.url ?? "");
    const title = String(resource.title ?? "Saved reader").slice(0, 200);
    if (!url.startsWith("https://") || hskLevel < 1 || hskLevel > 6) return [];
    const status = resource.status === "completed" ? "completed" : resource.status === "in_progress" ? "in_progress" : "new";
    const recap = String(resource.recap ?? "").slice(0, 8_000);
    const hardMatch = recap.match(/Hard words?:\s*(.+?)(?:\.\s|$)/i);
    const hardWords = hardMatch?.[1]?.trim().slice(0, 2_000) ?? "";
    const id = `local-${resourceId.replace(/[^a-zA-Z0-9-]/g, "-").slice(0, 65)}`;
    const openedAt = typeof resource.opened_ts === "string" ? resource.opened_ts : null;
    const completedAt = status === "completed" && typeof resource.completed_ts === "string" ? resource.completed_ts : null;
    const updatedAt = typeof resource.updated_ts === "string" ? resource.updated_ts : now;
    return [env.DB.prepare(
      `INSERT INTO external_readings
         (id,user_id,provider,hsk_level,title,url,status,hard_words,notes,opened_at,completed_at,created_at,updated_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
       ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,hsk_level=excluded.hsk_level,
         title=excluded.title,url=excluded.url,status=excluded.status,hard_words=excluded.hard_words,
         notes=excluded.notes,opened_at=excluded.opened_at,completed_at=excluded.completed_at,
         updated_at=excluded.updated_at WHERE external_readings.user_id=excluded.user_id
           AND excluded.updated_at>=external_readings.updated_at`,
    ).bind(id,user.id,provider,hskLevel,title,url,status,hardWords,recap,openedAt,completedAt,updatedAt,updatedAt)];
  });
  await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO learner_import_backup (user_id, schema_version, export_json, imported_at)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(user_id) DO UPDATE SET schema_version=excluded.schema_version,
         export_json=excluded.export_json, imported_at=excluded.imported_at`,
    ).bind(user.id, schemaVersion, serialized, now),
    env.DB.prepare(
      `INSERT INTO learner_progress (user_id, schema_version, progress_json, updated_at)
       VALUES (?, 2, ?, ?)
       ON CONFLICT(user_id) DO UPDATE SET schema_version=2,
         progress_json=excluded.progress_json, updated_at=excluded.updated_at`,
    ).bind(user.id, JSON.stringify(progress), now),
    ...externalStatements,
  ]);

  return NextResponse.json({
    ok: true,
    progress,
    imported: {
      vocabulary: Object.keys(vocabulary).length,
      reviews: rows(payload.review_log).length,
      stories: Object.keys(stories).length,
      grammar: Object.keys(grammar).length,
      externalReadings: externalStatements.length,
    },
  });
}

function boundedInteger(value: unknown, minimum: number, maximum: number) {
  const number = Number(value);
  if (!Number.isInteger(number)) return minimum;
  return Math.max(minimum, Math.min(maximum, number));
}

function retrievabilityScore(state: RecordValue) {
  const stability = Number(state.stability);
  const lastReview = typeof state.last_review_ts === "string" ? Date.parse(state.last_review_ts) : Number.NaN;
  if (!Number.isFinite(stability) || stability <= 0 || !Number.isFinite(lastReview)) return undefined;
  const elapsedDays = Math.max(0, (Date.now() - lastReview) / 86_400_000);
  const score = 100 * Math.pow(1 + (19 / 81) * elapsedDays / stability, -0.5);
  return Math.max(0, Math.min(100, Math.round(score)));
}
