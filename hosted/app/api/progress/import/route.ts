import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../../chatgpt-auth";
import content from "../../../hanlu-data.json";

export const dynamic = "force-dynamic";

type RecordValue = Record<string, unknown>;
type VocabularySummary = {
  listeningScore?: number;
  readingScore?: number;
  practices: number;
  lastReviewTs?: string;
  needsPractice?: boolean;
  known?: boolean;
};

function record(value: unknown): value is RecordValue {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function rows(value: unknown): RecordValue[] {
  return Array.isArray(value) ? value.filter(record) : [];
}

export async function POST(request: Request) {
  const user = await getChatGPTUser();
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
    vocabulary[id] = { ...(vocabulary[id] ?? { practices: 0 }), needsPractice: true, known: false };
  }

  const stories: Record<string, RecordValue> = {};
  for (const state of rows(payload.story_state)) {
    const story = storyByTitle.get(String(state.title_zh ?? ""));
    if (!story) continue;
    stories[String(story.id)] = {
      sentenceIndex: boundedInteger(state.current_index, 0, Math.max(0, story.sentences.length - 1)),
      status: ["new", "reading", "finished"].includes(String(state.status)) ? state.status : "new",
      ...(state.status === "finished" ? { completedAt: String(state.updated_ts ?? new Date().toISOString()) } : {}),
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
    stories[id] = state;
  }

  const grammar: Record<string, "new" | "practicing" | "learned"> = {};
  for (const state of rows(payload.grammar_state)) {
    const lesson = grammarByTitle.get(`${Number(state.level)}:${String(state.title_en ?? "")}`);
    if (!lesson) continue;
    const status = String(state.status);
    grammar[String(lesson.id)] = status === "learned" ? "learned" : status === "practicing" ? "practicing" : "new";
  }
  for (const attempt of rows(payload.grammar_attempt)) {
    const lesson = grammarByTitle.get(`${Number(attempt.level)}:${String(attempt.title_en ?? "")}`);
    if (lesson && !grammar[String(lesson.id)]) grammar[String(lesson.id)] = "practicing";
  }

  const progress = { version: 2, declaredHskBand, stories, grammar, vocabulary };
  const now = new Date().toISOString();
  const { env } = await import("cloudflare:workers");
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
  ]);

  return NextResponse.json({
    ok: true,
    progress,
    imported: {
      vocabulary: Object.keys(vocabulary).length,
      reviews: rows(payload.review_log).length,
      stories: Object.keys(stories).length,
      grammar: Object.keys(grammar).length,
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
