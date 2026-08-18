CREATE TABLE `learner_progress` (
	`user_id` text PRIMARY KEY NOT NULL,
	`schema_version` integer DEFAULT 1 NOT NULL,
	`progress_json` text NOT NULL,
	`updated_at` text NOT NULL
);
