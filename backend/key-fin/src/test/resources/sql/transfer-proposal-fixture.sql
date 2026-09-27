INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (986, 'transfer@keyfin.io', 'x', '이체테스터', 'test-user-key-986'),
 (985, 'noincome@keyfin.io', 'x', '수입계좌없음', 'test-user-key-985');

-- 9506: 수입 계좌(from) / 9504: 생활비 출금 계좌 잔액 500,000 / 9505: 월세통장 잔액 100,000 / 9507: 985의 출금 계좌(수입 계좌 없음)
INSERT INTO accounts (id, user_id, fin_account_no, bank_code, bank_name, alias, balance, balance_updated_at, is_managed, is_income) VALUES
 (9506, 986, '0019860000000006', '001', '한국은행', '월급통장', 1000000, '2026-09-10 09:00:00', TRUE, TRUE),
 (9504, 986, '0019860000000001', '001', '한국은행', '생활비',    500000, '2026-09-10 09:00:00', TRUE, FALSE),
 (9505, 986, '0019860000000002', '001', '한국은행', '월세통장',  100000, '2026-09-10 09:00:00', TRUE, FALSE),
 (9507, 985, '0019850000000001', '001', '한국은행', '생활비',     10000, '2026-09-10 09:00:00', TRUE, FALSE);

-- 카드 9603: 출금 요일 4(목) → 9/7 발행 청구서 출금일 9/10(오늘). 청구 80,000 + 학원비 550,000 이 같은 계좌(9504, 잔액 500,000)
INSERT INTO cards (id, user_id, fin_card_no_enc, cvc, issuer_code, card_name, withdrawal_account_id, withdrawal_weekday, is_managed) VALUES
 (9603, 986, '1001986100000003', '333', '1001', '신한 테스트카드', 9504, 4, TRUE);

INSERT INTO card_billings (id, card_id, billing_date, total_amount, status, paid_at) VALUES
 (9802, 9603, '2026-09-07', 80000, 'UNPAID', NULL);

-- 오늘 9/10: 학원비 550,000(9504) → 날짜순으로 카드 청구 80,000보다 먼저 판정(금액 내림차순) → 부족 50,000, 카드 청구는 잔액 0 → 부족 80,000
-- 내일 9/11: 보험료 60,000(9505, 잔액 100,000) → 준비됨 / 9/15 월세는 창 밖
INSERT INTO fixed_expenses (id, user_id, name, expense_type, amount, is_variable, payment_day, withdrawal_account_id, fin_subscription_id, active) VALUES
 (9710, 986, '학원비', 'UTILITY', 550000, FALSE, 10, 9504, NULL, TRUE),
 (9711, 986, '보험료', 'UTILITY',  60000, FALSE, 11, 9505, NULL, TRUE),
 (9704, 986, '월세',   'RENT',    490000, FALSE, 15, 9504, NULL, TRUE),
 (9712, 985, '학원비', 'UTILITY',  50000, FALSE, 10, 9507, NULL, TRUE);

-- 기존 제안: 9901 학원비(출금 9/10) 40,000(→ 50,000 갱신) / 9902 보험료(출금 9/11, 어제 D-1 제안 → 부족액 해소로 취소) /
-- 9903 월세(출금 9/8) 만료(→ 출금일 경과 취소) / 9904 이미 실행됨(불변) / 9905 카드 청구 9802가 어제 취소됨(→ 다시 부족해도 재제안 없음)
INSERT INTO prepare_transfers (id, user_id, fixed_expense_id, card_billing_id, scheduled_date, due_date, required_amount, from_account_id, to_account_id, status, institution_tx_no, executed_at, fail_reason) VALUES
 (9901, 986, 9710, NULL, '2026-09-09', '2026-09-10',  40000, 9506, 9504, 'PROPOSED', NULL, NULL, NULL),
 (9902, 986, 9711, NULL, '2026-09-09', '2026-09-11',  60000, 9506, 9505, 'PROPOSED', NULL, NULL, NULL),
 (9903, 986, 9704, NULL, '2026-09-07', '2026-09-08', 100000, 9506, 9504, 'PROPOSED', NULL, NULL, NULL),
 (9904, 986, 9704, NULL, '2026-08-13', '2026-08-14', 200000, 9506, 9504, 'EXECUTED', '20260814083000000001', '2026-08-14 08:31:00', NULL),
 (9905, 986, NULL, 9802, '2026-09-09', '2026-09-10',  30000, 9506, 9504, 'CANCELED', NULL, NULL, '부족액 해소');
