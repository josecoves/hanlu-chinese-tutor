CREATE TABLE `external_readings` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`provider` text NOT NULL,
	`hsk_level` integer NOT NULL,
	`title` text NOT NULL,
	`url` text NOT NULL,
	`status` text DEFAULT 'new' NOT NULL,
	`hard_words` text DEFAULT '' NOT NULL,
	`notes` text DEFAULT '' NOT NULL,
	`opened_at` text,
	`completed_at` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_external_readings_user_updated` ON `external_readings` (`user_id`,`updated_at`);--> statement-breakpoint
CREATE TABLE `grammar_attempts` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`grammar_id` integer NOT NULL,
	`direction` text NOT NULL,
	`prompt_text` text NOT NULL,
	`response_text` text NOT NULL,
	`expected_text` text NOT NULL,
	`verdict` text DEFAULT 'pending' NOT NULL,
	`feedback_json` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_grammar_attempts_user_updated` ON `grammar_attempts` (`user_id`,`updated_at`);--> statement-breakpoint
CREATE INDEX `idx_grammar_attempts_user_grammar` ON `grammar_attempts` (`user_id`,`grammar_id`);--> statement-breakpoint
CREATE TABLE `learning_reports` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`kind` text NOT NULL,
	`reference_id` text NOT NULL,
	`note` text NOT NULL,
	`context_json` text DEFAULT '{}' NOT NULL,
	`status` text DEFAULT 'open' NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_learning_reports_user_created` ON `learning_reports` (`user_id`,`created_at`);