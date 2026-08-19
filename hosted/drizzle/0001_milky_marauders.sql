CREATE TABLE `writing_ai_usage` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`usage_date` text NOT NULL,
	`reserved_micro_usd` integer NOT NULL,
	`status` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `writing_attempts` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`mode` text NOT NULL,
	`hsk_level` integer NOT NULL,
	`prompt_text` text NOT NULL,
	`response_text` text NOT NULL,
	`target_words_json` text DEFAULT '[]' NOT NULL,
	`feedback_json` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
