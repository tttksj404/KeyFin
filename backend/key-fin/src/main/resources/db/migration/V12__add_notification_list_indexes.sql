ALTER TABLE `notifications`
	ADD INDEX `idx_noti_user_id` (`user_id`, `id`),
	ADD INDEX `idx_noti_user_read_id` (`user_id`, `is_read`, `id`);
