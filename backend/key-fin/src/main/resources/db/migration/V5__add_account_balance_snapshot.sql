ALTER TABLE `accounts`
	ADD COLUMN `bank_name` VARCHAR(20) NOT NULL COMMENT '은행명' AFTER `bank_code`,
	ADD COLUMN `balance` BIGINT NOT NULL COMMENT '마지막 확인 잔액' AFTER `alias`,
	ADD COLUMN `balance_updated_at` DATETIME NOT NULL COMMENT '잔액 업데이트 시각' AFTER `balance`;
