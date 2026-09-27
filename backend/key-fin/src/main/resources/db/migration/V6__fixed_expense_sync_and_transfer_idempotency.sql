-- 금융망 정기결제 동기화 항목은 카드 청구 경로로 나가는 돈이라 별도 출금 계좌가 없음(2026.9.13 실험: 구독 결제는 카드 거래로 기록되어 청구서에 합산).
-- 수동 등록 항목의 출금 계좌 필수는 앱(FixedExpenseRequest @NotNull)이 보장.
ALTER TABLE `fixed_expenses`
	MODIFY `withdrawal_account_id` BIGINT NULL
		COMMENT '출금 계좌 ID — 수동 항목 필수, 금융망 동기화 구독은 NULL(카드 청구에 포함)',
	ADD CONSTRAINT `uq_fe_subscription` UNIQUE (`user_id`, `fin_subscription_id`);

-- 무중단 배포 중 결제 준비 배치가 신·구 인스턴스에서 동시에 돌아도 같은 고정지출·같은 날짜의 제안은 1건만 남는다(NFR-OPS-01 멱등 키 보강).
ALTER TABLE `prepare_transfers`
	ADD CONSTRAINT `uq_pt_schedule` UNIQUE (`fixed_expense_id`, `scheduled_date`);
