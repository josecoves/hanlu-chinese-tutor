CREATE INDEX `idx_writing_ai_usage_date` ON `writing_ai_usage` (`usage_date`);--> statement-breakpoint
CREATE INDEX `idx_writing_ai_usage_user_created` ON `writing_ai_usage` (`user_id`,`created_at`);--> statement-breakpoint
CREATE INDEX `idx_writing_attempts_user_updated` ON `writing_attempts` (`user_id`,`updated_at`);