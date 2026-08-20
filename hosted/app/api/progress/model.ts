export type StoredStoryProgress = {
  sentenceIndex: number;
  status?: "new" | "reading" | "finished";
  completedAt?: string;
  completedSentences?: number[];
  hardWords?: Record<string, number[]>;
  updatedAt?: string;
};

export type StoredVocabularyProgress = {
  listeningScore?: number;
  readingScore?: number;
  practices: number;
  lastReviewTs?: string;
  needsPractice?: boolean;
  known?: boolean;
  updatedAt?: string;
};

export type StoredProgress = {
  version: 2;
  declaredHskBand: number;
  stories: Record<string, StoredStoryProgress>;
  grammar: Record<string, "new" | "practicing" | "learned">;
  grammarUpdatedAt?: Record<string, string>;
  vocabulary: Record<string, StoredVocabularyProgress>;
};

export const EMPTY_PROGRESS: StoredProgress = {
  version: 2,
  declaredHskBand: 0,
  stories: {},
  grammar: {},
  grammarUpdatedAt: {},
  vocabulary: {},
};

export function normalizeProgress(value: unknown): StoredProgress | null {
  if (!isPlainRecord(value)) return null;
  const candidate = value;
  if (candidate.version === 1) {
    return normalizeProgress({
      version: 2,
      declaredHskBand: 0,
      stories: candidate.stories,
      grammar: candidate.grammar,
      vocabulary: {},
    });
  }
  if (candidate.version !== 2 || !isPlainRecord(candidate.stories) ||
      !isPlainRecord(candidate.grammar) || !isPlainRecord(candidate.vocabulary)) return null;

  const stories: StoredProgress["stories"] = {};
  for (const [id, raw] of Object.entries(candidate.stories)) {
    if (!isValidId(id) || !isPlainRecord(raw)) return null;
    const sentenceIndex = Number(raw.sentenceIndex);
    if (!Number.isInteger(sentenceIndex) || sentenceIndex < 0 || sentenceIndex > 1_000) return null;
    const completedSentences = Array.isArray(raw.completedSentences)
      ? [...new Set(raw.completedSentences.filter((item): item is number =>
          Number.isInteger(item) && Number(item) >= 0 && Number(item) <= 1_000))].slice(0, 1_000)
      : [];
    const hardWords: Record<string, number[]> = {};
    if (isPlainRecord(raw.hardWords)) {
      for (const [sentence, ids] of Object.entries(raw.hardWords)) {
        if (!/^\d{1,4}$/.test(sentence) || !Array.isArray(ids)) continue;
        hardWords[sentence] = [...new Set(ids.filter((item): item is number =>
          Number.isInteger(item) && Number(item) > 0))].slice(0, 500);
      }
    }
    const status = ["new", "reading", "finished"].includes(String(raw.status))
      ? raw.status as StoredStoryProgress["status"] : undefined;
    stories[id] = {
      sentenceIndex,
      ...(status ? { status } : {}),
      ...(typeof raw.completedAt === "string" ? { completedAt: raw.completedAt } : {}),
      ...(completedSentences.length ? { completedSentences: completedSentences.sort((a, b) => a - b) } : {}),
      ...(Object.keys(hardWords).length ? { hardWords } : {}),
      ...(typeof raw.updatedAt === "string" ? { updatedAt: raw.updatedAt } : {}),
    };
  }

  const grammar: StoredProgress["grammar"] = {};
  for (const [id, status] of Object.entries(candidate.grammar)) {
    if (!isValidId(id) || !["new", "practicing", "learned"].includes(String(status))) return null;
    grammar[id] = status as StoredProgress["grammar"][string];
  }
  const grammarUpdatedAt: Record<string, string> = {};
  if (isPlainRecord(candidate.grammarUpdatedAt)) {
    for (const [id, updatedAt] of Object.entries(candidate.grammarUpdatedAt)) {
      if (isValidId(id) && typeof updatedAt === "string") grammarUpdatedAt[id] = updatedAt;
    }
  }

  const vocabulary: StoredProgress["vocabulary"] = {};
  for (const [id, raw] of Object.entries(candidate.vocabulary)) {
    if (!isValidId(id) || !isPlainRecord(raw)) return null;
    const practices = Number(raw.practices ?? 0);
    if (!Number.isInteger(practices) || practices < 0 || practices > 1_000_000) return null;
    const listeningScore = validScore(raw.listeningScore);
    const readingScore = validScore(raw.readingScore);
    vocabulary[id] = {
      practices,
      ...(listeningScore !== undefined ? { listeningScore } : {}),
      ...(readingScore !== undefined ? { readingScore } : {}),
      ...(typeof raw.lastReviewTs === "string" ? { lastReviewTs: raw.lastReviewTs } : {}),
      ...(typeof raw.needsPractice === "boolean" ? { needsPractice: raw.needsPractice } : {}),
      ...(typeof raw.known === "boolean" ? { known: raw.known } : {}),
      ...(typeof raw.updatedAt === "string" ? { updatedAt: raw.updatedAt } : {}),
    };
  }

  return {
    version: 2,
    declaredHskBand: [0, 1, 2, 3].includes(Number(candidate.declaredHskBand))
      ? Number(candidate.declaredHskBand) : 0,
    stories,
    grammar,
    grammarUpdatedAt,
    vocabulary,
  };
}

/** Merge independent devices without silently discarding completed work. */
export function mergeProgress(current: StoredProgress, incoming: StoredProgress): StoredProgress {
  const stories = { ...current.stories };
  for (const [id, next] of Object.entries(incoming.stories)) {
    const previous = stories[id];
    if (!previous) { stories[id] = next; continue; }
    const nextIsNewer = timestamp(next.updatedAt) >= timestamp(previous.updatedAt);
    const preferred = nextIsNewer ? next : previous;
    const completedSentences = [...new Set([
      ...(previous.completedSentences ?? []), ...(next.completedSentences ?? []),
    ])].sort((a, b) => a - b);
    const hardWords: Record<string, number[]> = {};
    for (const source of [previous.hardWords ?? {}, next.hardWords ?? {}]) {
      for (const [sentence, ids] of Object.entries(source)) {
        hardWords[sentence] = [...new Set([...(hardWords[sentence] ?? []), ...ids])];
      }
    }
    stories[id] = {
      ...preferred,
      sentenceIndex: Math.max(previous.sentenceIndex, next.sentenceIndex),
      ...(completedSentences.length ? { completedSentences } : {}),
      ...(Object.keys(hardWords).length ? { hardWords } : {}),
      ...(previous.completedAt || next.completedAt
        ? { completedAt: latestTimestamp(previous.completedAt, next.completedAt) } : {}),
      updatedAt: latestTimestamp(previous.updatedAt, next.updatedAt),
    };
  }

  const grammar = { ...current.grammar };
  const grammarUpdatedAt = { ...(current.grammarUpdatedAt ?? {}) };
  for (const [id, status] of Object.entries(incoming.grammar)) {
    const currentTs = grammarUpdatedAt[id];
    const incomingTs = incoming.grammarUpdatedAt?.[id];
    if (!(id in grammar) || timestamp(incomingTs) >= timestamp(currentTs)) {
      grammar[id] = status;
      if (incomingTs) grammarUpdatedAt[id] = incomingTs;
    }
  }

  const vocabulary = { ...current.vocabulary };
  for (const [id, next] of Object.entries(incoming.vocabulary)) {
    const previous = vocabulary[id];
    if (!previous) { vocabulary[id] = next; continue; }
    const nextIsNewer = timestamp(next.updatedAt ?? next.lastReviewTs) >=
      timestamp(previous.updatedAt ?? previous.lastReviewTs);
    const preferred = nextIsNewer ? next : previous;
    vocabulary[id] = {
      ...preferred,
      practices: Math.max(previous.practices, next.practices),
      lastReviewTs: latestTimestamp(previous.lastReviewTs, next.lastReviewTs),
      updatedAt: latestTimestamp(previous.updatedAt, next.updatedAt),
    };
  }

  return {
    version: 2,
    declaredHskBand: incoming.declaredHskBand,
    stories,
    grammar,
    grammarUpdatedAt,
    vocabulary,
  };
}

function validScore(value: unknown) {
  const score = Number(value);
  return Number.isFinite(score) && score >= 0 && score <= 100 ? Math.round(score) : undefined;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isValidId(value: string) {
  return /^\d{1,8}$/.test(value);
}

function timestamp(value?: string) {
  const parsed = value ? Date.parse(value) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : 0;
}

function latestTimestamp(left?: string, right?: string) {
  if (!left) return right;
  if (!right) return left;
  return timestamp(right) >= timestamp(left) ? right : left;
}
