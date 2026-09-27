INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (986, 'sync-connected@keyfin.io', 'x', '동기화테스터', 'test-user-key-986'),
 (985, 'sync-unlinked@keyfin.io', 'x', '미연결테스터', NULL);

INSERT INTO accounts (id, user_id, fin_account_no, bank_code, bank_name, alias, balance, balance_updated_at, is_managed, is_income) VALUES
 (9504, 986, '0019860000000001', '001', '한국은행', '생활비', 500000, '2026-09-10 09:00:00', TRUE, TRUE);

-- 9701: 동기화·활성 (금융망에 계속 ACTIVE → 갱신) / 9702: 동기화·활성 (금융망 목록에서 사라짐 → 비활성) /
-- 9703: 동기화·비활성 (금융망에서 다시 ACTIVE → 되살림) / 9704: 수동·활성 (동기화가 건드리지 않음)
-- 9705: 수동·변동형·출금일 31 (캘린더 말일 보정 + estimated) / 9706: 수동·삭제됨 (캘린더에서 제외)
INSERT INTO fixed_expenses (id, user_id, name, expense_type, amount, is_variable, payment_day, withdrawal_account_id, fin_subscription_id, active) VALUES
 (9701, 986, 'FLO',      'SUBSCRIPTION',  8900, FALSE, 13, NULL, 'SUB-FLO',     TRUE),
 (9702, 986, '왓챠',     'SUBSCRIPTION',  7900, FALSE,  5, NULL, 'SUB-WATCHA',  TRUE),
 (9703, 986, '멜론',     'SUBSCRIPTION', 10900, FALSE, 20, NULL, 'SUB-MELON',   FALSE),
 (9704, 986, '월세',     'RENT',        550000, FALSE, 15, 9504, NULL,          TRUE),
 (9705, 986, '통신비',   'UTILITY',      45000, TRUE,  31, 9504, NULL,          TRUE),
 (9706, 986, '헬스장',   'SUBSCRIPTION', 60000, FALSE,  1, 9504, NULL,          FALSE);
