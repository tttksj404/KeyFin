CREATE TABLE `transaction_sync_states` (
	`id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '고유 ID',
	`user_id` BIGINT NOT NULL COMMENT '사용자 ID',
	`asset_type` VARCHAR(10) NOT NULL COMMENT '동기화 자산 종류 — ACCOUNT/CARD',
	`asset_id` BIGINT NOT NULL COMMENT '동기화 대상 계좌 또는 카드 ID',
	`last_synced_at` DATETIME NULL COMMENT '마지막 성공 거래 동기화 시각',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성 시각',
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_transaction_sync_state` UNIQUE (`user_id`, `asset_type`, `asset_id`),
	CONSTRAINT `fk_transaction_sync_state_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
	INDEX `idx_transaction_sync_state_asset` (`asset_type`, `asset_id`)
) COMMENT='거래 동기화 상태';

