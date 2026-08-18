import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

/** One compact, private learning-state document per signed-in learner. */
export const learnerProgress = sqliteTable("learner_progress", {
  userId: text("user_id").primaryKey(),
  schemaVersion: integer("schema_version").notNull().default(1),
  progressJson: text("progress_json").notNull(),
  updatedAt: text("updated_at").notNull(),
});
