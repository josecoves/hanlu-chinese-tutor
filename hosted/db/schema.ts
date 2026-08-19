import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

/** One compact, private learning-state document per signed-in learner. */
export const learnerProgress = sqliteTable("learner_progress", {
  userId: text("user_id").primaryKey(),
  schemaVersion: integer("schema_version").notNull().default(1),
  progressJson: text("progress_json").notNull(),
  updatedAt: text("updated_at").notNull(),
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
