-- 카드 청구 출금일은 요일 기준(금융망 withdrawalDate). 카드 연결 시 금융망 카드 목록 응답에서 기록한다.
ALTER TABLE `cards`
	ADD COLUMN `withdrawal_weekday` TINYINT NULL
		COMMENT '청구 출금 요일 — 금융망 withdrawalDate (1=월 … 7=일). 청구서 발행일(월) + (요일-1) = 출금일' AFTER `withdrawal_account_id`,
	ADD CONSTRAINT `chk_cards_weekday` CHECK (`withdrawal_weekday` IS NULL OR `withdrawal_weekday` BETWEEN 1 AND 7);
