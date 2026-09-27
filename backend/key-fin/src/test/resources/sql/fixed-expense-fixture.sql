INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (988, 'fixed-owner@keyfin.io', 'x', '고정지출테스터', 'test-user-key-988'),
 (987, 'fixed-other@keyfin.io', 'x', '고정지출타인', 'test-user-key-987');

-- 9501: 988의 관리 계좌 / 9502: 988의 미관리 계좌 / 9503: 987의 관리 계좌
INSERT INTO accounts (id, user_id, fin_account_no, bank_code, bank_name, alias, balance, balance_updated_at, is_managed, is_income) VALUES
 (9501, 988, '0019880000000001', '001', '한국은행', '생활비', 1000000, '2026-09-10 09:00:00', TRUE,  TRUE),
 (9502, 988, '0019880000000002', '001', '한국은행', '비관리', 0,       '2026-09-10 09:00:00', FALSE, FALSE),
 (9503, 987, '0019870000000001', '001', '한국은행', '타인',   0,       '2026-09-10 09:00:00', TRUE,  FALSE);

-- 9701: 988의 관리 카드 / 9702: 988의 미관리 카드 / 9703: 987의 관리 카드
INSERT INTO cards (id, user_id, fin_card_no_enc, cvc, issuer_code, card_name, withdrawal_account_id, withdrawal_weekday, is_managed) VALUES
 (9701, 988, '9880000000000001', '111', '1001', '관리카드',   9501, 3,    TRUE),
 (9702, 988, '9880000000000002', '222', '1001', '미관리카드', NULL, NULL, FALSE),
 (9703, 987, '9870000000000001', '333', '1001', '타인카드',   9503, 3,    TRUE);

-- 9601: 수동·활성 / 9602: 금융망 동기화 항목(수정·삭제 불가) / 9603: 수동·삭제됨(재등록 중복 검사에서 제외)
INSERT INTO fixed_expenses (id, user_id, name, expense_type, amount, is_variable, payment_day, withdrawal_account_id, fin_subscription_id, active) VALUES
 (9601, 988, '월세',    'RENT',         550000, FALSE, 15, 9501, NULL,                    TRUE),
 (9602, 988, 'FLO 개인', 'SUBSCRIPTION',   7900, FALSE, 15, 9501, 'SUB20260810103000123', TRUE),
 (9603, 988, '헬스장',  'SUBSCRIPTION',  60000, FALSE,  1, 9501, NULL,                    FALSE);
