INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (986, 'approve@keyfin.io',   'x', '승인테스터',     'test-user-key-986'),
 (987, 'noconsent@keyfin.io', 'x', '동의안함',       'test-user-key-987'),
 (988, 'badfrom@keyfin.io',   'x', '출금계좌부적격', 'test-user-key-988');

-- 986: 동의 ON, 1회 300,000 · 1일 800,000 / 987: 동의 OFF / 988: 동의 ON, 한도 없음
INSERT INTO user_settings (user_id, transfer_consent, transfer_limit_once, transfer_limit_daily) VALUES
 (986, TRUE,  300000, 800000),
 (987, FALSE, NULL,   NULL),
 (988, TRUE,  NULL,   NULL);

INSERT INTO accounts (id, user_id, fin_account_no, bank_code, bank_name, alias, balance, balance_updated_at, is_managed, is_income) VALUES
 (9506, 986, '0019860000000006', '001', '한국은행', '월급통장', 1000000, '2026-09-10 09:00:00', TRUE, TRUE),
 (9504, 986, '0019860000000001', '001', '한국은행', '생활비',    200000, '2026-09-10 09:00:00', TRUE, FALSE),
 (9508, 987, '0019870000000001', '001', '한국은행', '월급통장',  900000, '2026-09-10 09:00:00', TRUE, TRUE),
 (9509, 987, '0019870000000002', '001', '한국은행', '생활비',     10000, '2026-09-10 09:00:00', TRUE, FALSE),
 (9510, 988, '0019880000000001', '001', '한국은행', '적금통장',  900000, '2026-09-10 09:00:00', TRUE, FALSE),
 (9511, 988, '0019880000000002', '001', '한국은행', '생활비',     10000, '2026-09-10 09:00:00', TRUE, FALSE);

INSERT INTO cards (id, user_id, fin_card_no_enc, cvc, issuer_code, card_name, withdrawal_account_id, withdrawal_weekday, is_managed) VALUES
 (9603, 986, '1001986100000003', '333', '1001', '신한 테스트카드', 9504, 4, TRUE);

INSERT INTO card_billings (id, card_id, billing_date, total_amount, status, paid_at) VALUES
 (9802, 9603, '2026-09-07', 300000, 'UNPAID', NULL);

INSERT INTO fixed_expenses (id, user_id, name, expense_type, amount, is_variable, payment_day, withdrawal_account_id, fin_subscription_id, active) VALUES
 (9704, 986, '월세',   'RENT',    490000, FALSE, 15, 9504, NULL, TRUE),
 (9713, 987, '학원비', 'UTILITY',  50000, FALSE, 11, 9509, NULL, TRUE),
 (9714, 988, '보험료', 'UTILITY',  50000, FALSE, 11, 9511, NULL, TRUE);

-- 오늘(고정 시계) 2026-09-10
-- 9901 정상 승인(230,000) / 9902 1회 한도 초과(350,000) / 9903 카드 청구 300,000 — 오늘 실행 550,000 + 300,000 > 1일 800,000
-- 9904 옛 실행분 / 9905 APPROVED로 남은 건(응답 유실) — 같은 번호로 재시도 / 9906 오늘 실행 550,000 / 9907 동의 OFF 사용자 / 9908 출금 계좌 부적격 / 9909 FAILED(재승인 불가)
INSERT INTO prepare_transfers (id, user_id, fixed_expense_id, card_billing_id, scheduled_date, due_date, required_amount, from_account_id, to_account_id, status, institution_tx_no, executed_at, fail_reason) VALUES
 (9901, 986, 9704, NULL, '2026-09-14', '2026-09-15', 230000, 9506, 9504, 'PROPOSED', NULL, NULL, NULL),
 (9902, 986, 9704, NULL, '2026-09-21', '2026-09-22', 350000, 9506, 9504, 'PROPOSED', NULL, NULL, NULL),
 (9903, 986, NULL, 9802, '2026-09-10', '2026-09-10', 300000, 9506, 9504, 'PROPOSED', NULL, NULL, NULL),
 (9904, 986, 9704, NULL, '2026-09-07', '2026-09-08', 200000, 9506, 9504, 'EXECUTED', '20260907083000000004', '2026-09-07 08:40:00', NULL),
 (9905, 986, 9704, NULL, '2026-08-31', '2026-09-01', 120000, 9506, 9504, 'APPROVED', '20260901083000000009', NULL, NULL),
 (9906, 986, 9704, NULL, '2026-09-09', '2026-09-10', 550000, 9506, 9504, 'EXECUTED', '20260910083000000006', '2026-09-10 08:40:00', NULL),
 (9907, 987, 9713, NULL, '2026-09-10', '2026-09-11',  50000, 9508, 9509, 'PROPOSED', NULL, NULL, NULL),
 (9908, 988, 9714, NULL, '2026-09-10', '2026-09-11',  50000, 9510, 9511, 'PROPOSED', NULL, NULL, NULL),
 (9909, 986, 9704, NULL, '2026-09-28', '2026-09-29', 100000, 9506, 9504, 'FAILED', '20260928083000000009', NULL, 'A1014 출금 계좌 잔액 부족');
