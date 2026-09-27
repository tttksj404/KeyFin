INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (986, 'sync-connected@keyfin.io', 'x', '동기화테스터', 'test-user-key-986'),
 (985, 'sync-unlinked@keyfin.io', 'x', '미연결테스터', NULL);

INSERT INTO accounts (id, user_id, fin_account_no, bank_code, bank_name, alias, balance, balance_updated_at, is_managed, is_income) VALUES
 (9504, 986, '0019860000000001', '001', '한국은행', '생활비', 500000, '2026-09-10 09:00:00', TRUE, TRUE),
 (9505, 986, '0019860000000002', '001', '한국은행', '월세통장', 100000, '2026-09-10 09:00:00', TRUE, FALSE);

-- 9601: 관리 카드, 출금 계좌 9504, 출금 요일 미기록(V8 이전 연결) / 9602: 미관리 카드(동기화 대상 아님) / 9603: 관리 카드, 출금 요일 3=수
INSERT INTO cards (id, user_id, fin_card_no_enc, cvc, issuer_code, card_name, withdrawal_account_id, withdrawal_weekday, is_managed) VALUES
 (9601, 986, '1001986100000001', '111', '1001', 'KB 테스트카드', 9504, NULL, TRUE),
 (9602, 986, '1001986100000002', '222', '1001', '미관리카드',    9504, NULL, FALSE),
 (9603, 986, '1001986100000003', '333', '1001', '신한 테스트카드', 9504, 3,    TRUE);

-- 9801: 이미 저장된 9/7 발행 청구서(미결제) — 동기화가 결제완료로 갱신해야 함
-- 9802/9803: 카드 9603(출금 요일 3=수) — 9/7 발행 미결제(출금 9/9, 과거), 8/31 발행 결제완료(9/2 납입)
INSERT INTO card_billings (id, card_id, billing_date, total_amount, status, paid_at) VALUES
 (9801, 9601, '2026-09-07', 42000, 'UNPAID', NULL),
 (9802, 9603, '2026-09-07', 80000, 'UNPAID', NULL),
 (9803, 9603, '2026-08-31', 30000, 'PAID',   '2026-09-02 16:00:00');

-- 카드 9603 이번 주(9/7~) LIVE 승인: 9000 + 6000 = 15000 예정액. 취소·SEED·지난주 거래는 제외
INSERT INTO transactions (id, user_id, source, tx_type, card_id, amount, tx_date, tx_time, confirm_status, exclude_tag, status) VALUES
 (9901, 986, 'LIVE', 'CARD', 9603,  9000, '2026-09-08', '12:10:00', 'AUTO', 'NONE', 'NORMAL'),
 (9902, 986, 'LIVE', 'CARD', 9603,  6000, '2026-09-09', '12:15:00', 'AUTO', 'NONE', 'NORMAL'),
 (9903, 986, 'LIVE', 'CARD', 9603,  5000, '2026-09-09', '13:00:00', 'AUTO', 'NONE', 'CANCELED'),
 (9904, 986, 'SEED', 'CARD', 9603, 20000, '2026-09-08', '09:00:00', 'AUTO', 'NONE', 'NORMAL'),
 (9905, 986, 'LIVE', 'CARD', 9603, 10000, '2026-09-06', '09:00:00', 'AUTO', 'NONE', 'NORMAL');

-- 캘린더 합류용 고정지출: 월세(9504, 15일) · 통신비(9505, 20일) · 동기화 구독(FLO, 13일)
INSERT INTO fixed_expenses (id, user_id, name, expense_type, amount, is_variable, payment_day, withdrawal_account_id, fin_subscription_id, active) VALUES
 (9701, 986, 'FLO',    'SUBSCRIPTION',   8900, FALSE, 13, NULL, 'SUB-FLO', TRUE),
 (9704, 986, '월세',   'RENT',         490000, FALSE, 15, 9504, NULL,      TRUE),
 (9705, 986, '통신비', 'UTILITY',       45000, TRUE,  20, 9505, NULL,      TRUE);
