-- 금융망 정기결제 목록·이력 조회 응답에는 결제 카드번호가 없음(변경 API 응답에만 마스킹 번호).
ALTER TABLE `fixed_expenses`
	ADD COLUMN `card_id` BIGINT NULL
		COMMENT '결제 카드 ID — 금융망 동기화 구독만, 단일 카드 자동 지정 또는 사용자 지정'
		AFTER `withdrawal_account_id`,
	ADD CONSTRAINT `fk_fe_card` FOREIGN KEY (`card_id`) REFERENCES `cards`(`id`);
