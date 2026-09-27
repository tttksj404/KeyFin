-- 결제 준비 이체의 대상은 고정지출 또는 카드 청구서 중 하나. 실행 예정일(scheduled_date)과 대상 출금일(due_date)을 분리한다(-41).
ALTER TABLE `prepare_transfers`
	ADD COLUMN `card_billing_id` BIGINT NULL COMMENT '대상 카드 청구서 ID — 고정지출과 둘 중 하나만' AFTER `fixed_expense_id`,
	ADD COLUMN `due_date` DATE NOT NULL COMMENT '대상 출금일 — 만료·중복 판정 기준. 실행 예정일은 보통 전날, 월요일 출금 카드는 당일' AFTER `scheduled_date`,
	DROP INDEX `uq_pt_schedule`,
	ADD CONSTRAINT `uq_pt_expense_due` UNIQUE (`fixed_expense_id`, `due_date`),
	ADD CONSTRAINT `uq_pt_billing` UNIQUE (`card_billing_id`),
	ADD CONSTRAINT `fk_pt_billing` FOREIGN KEY (`card_billing_id`) REFERENCES `card_billings`(`id`),
	ADD CONSTRAINT `chk_pt_purpose` CHECK ((`fixed_expense_id` IS NULL) <> (`card_billing_id` IS NULL));
