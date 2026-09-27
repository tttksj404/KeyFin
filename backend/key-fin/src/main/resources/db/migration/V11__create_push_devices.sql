CREATE TABLE `push_devices` (
	`id` BIGINT NOT NULL AUTO_INCREMENT,
	`user_id` BIGINT NOT NULL,
	`installation_id` VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
	`fcm_token` VARCHAR(2048) CHARACTER SET ascii COLLATE ascii_bin NULL,
	`platform` VARCHAR(10) NOT NULL,
	`active` BOOLEAN NOT NULL DEFAULT TRUE,
	`last_seen_at` DATETIME(6) NOT NULL,
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_push_device_installation` UNIQUE (`installation_id`),
	CONSTRAINT `uq_push_device_token` UNIQUE (`fcm_token`),
	CONSTRAINT `fk_push_device_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
	INDEX `idx_push_device_user_active` (`user_id`, `active`)
) COMMENT='사용자별 앱 설치와 푸시 토큰';
