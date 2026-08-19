import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

/** One compact, private learning-state document per signed-in learner. */
export const learnerProgress = sqliteTable("learner_progress", {
  userId: text("user_id").primaryKey(),
  schemaVersion: integer("schema_version").notNull().default(1),
  progressJson: text("progress_json").notNull(),
  updatedAt: text("updated_at").notNull(),
});

/** Exact private copy of the most recent local export, kept for lossless recovery. */
export const learnerImportBackup = sqliteTable("learner_import_backup", {
  userId: text("user_id").primaryKey(),
  schemaVersion: integer("schema_version").notNull(),
  exportJson: text("export_json").notNull(),
  importedAt: text("imported_at").notNull(),
});

/** Private writing drafts, submissions, and AI feedback for each learner. */
export const writingAttempts = sqliteTable(
  "writing_attempts",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    mode: text("mode").notNull(),
    hskLevel: integer("hsk_level").notNull(),
    promptText: text("prompt_text").notNull(),
    responseText: text("response_text").notNull(),
    targetWordsJson: text("target_words_json").notNull().default("[]"),
    feedbackJson: text("feedback_json"),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [index("idx_writing_attempts_user_updated").on(table.userId, table.updatedAt)],
);

/** Fixed-cost reservations enforce Hanlu's intentionally tiny daily AI budget. */
export const writingAiUsage = sqliteTable(
  "writing_ai_usage",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    usageDate: text("usage_date").notNull(),
    reservedMicroUsd: integer("reserved_micro_usd").notNull(),
    status: text("status").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("idx_writing_ai_usage_date").on(table.usageDate),
    index("idx_writing_ai_usage_user_created").on(table.userId, table.createdAt),
  ],
);

/** Links to external graded readers, plus the learner's private notes and status. */
export const externalReadings = sqliteTable(
  "external_readings",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    provider: text("provider").notNull(),
    hskLevel: integer("hsk_level").notNull(),
    title: text("title").notNull(),
    url: text("url").notNull(),
    status: text("status").notNull().default("new"),
    hardWords: text("hard_words").notNull().default(""),
    notes: text("notes").notNull().default(""),
    openedAt: text("opened_at"),
    completedAt: text("completed_at"),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [index("idx_external_readings_user_updated").on(table.userId, table.updatedAt)],
);

/** Cloud grammar attempts and optional AI verification. */
export const grammarAttempts = sqliteTable(
  "grammar_attempts",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    grammarId: integer("grammar_id").notNull(),
    direction: text("direction").notNull(),
    promptText: text("prompt_text").notNull(),
    responseText: text("response_text").notNull(),
    expectedText: text("expected_text").notNull(),
    verdict: text("verdict").notNull().default("pending"),
    feedbackJson: text("feedback_json"),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    index("idx_grammar_attempts_user_updated").on(table.userId, table.updatedAt),
    index("idx_grammar_attempts_user_grammar").on(table.userId, table.grammarId),
  ],
);

/** Learner flags for questionable exercises, grading, or source material. */
export const learningReports = sqliteTable(
  "learning_reports",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    kind: text("kind").notNull(),
    referenceId: text("reference_id").notNull(),
    note: text("note").notNull(),
    contextJson: text("context_json").notNull().default("{}"),
    status: text("status").notNull().default("open"),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("idx_learning_reports_user_created").on(table.userId, table.createdAt)],
);
