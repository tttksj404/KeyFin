INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (993, 'confirm-owner@keyfin.io', 'x', '확정테스터', 'test-user-key-993'),
 (992, 'confirm-other@keyfin.io', 'x', '타인테스터', 'test-user-key-992');

-- 9001: 승인 대상(PROPOSED), 9002: 이미 확정된 전 주기 예산(CONFIRMED)
INSERT INTO budgets (id, user_id, budget_month, status) VALUES
 (9001, 993, '202609', 'PROPOSED'),
 (9002, 993, '202608', 'CONFIRMED');

INSERT INTO budget_envelopes (id, budget_id, envelope_id, proposed_amount, confirmed_amount) VALUES
 (9101, 9001, 1, 300000, NULL),
 (9102, 9001, 2, 100000, NULL),
 (9103, 9001, 3,  50000, NULL),
 (9104, 9001, 4, 100000, NULL),
 (9105, 9001, 5, 100000, NULL),
 (9106, 9001, 6, 150000, NULL),
 (9107, 9001, 7,  50000, NULL),
 (9201, 9002, 1, 300000, 280000),
 (9202, 9002, 2, 100000, 100000),
 (9203, 9002, 3,  50000,  50000),
 (9204, 9002, 4, 100000, 100000),
 (9205, 9002, 5, 100000, 100000),
 (9206, 9002, 6, 150000, 150000),
 (9207, 9002, 7,  50000,  50000);
