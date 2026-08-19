CREATE TABLE `learner_import_backup` (
	`user_id` text PRIMARY KEY NOT NULL,
	`schema_version` integer NOT NULL,
	`export_json` text NOT NULL,
	`imported_at` text NOT NULL
);
