INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (991, 'board-confirmed@keyfin.io', 'x', '보드확정테스터', 'test-user-key-991'),
 (990, 'board-empty@keyfin.io', 'x', '보드무예산테스터', 'test-user-key-990'),
 (989, 'board-anchor23@keyfin.io', 'x', '기준일23테스터', 'test-user-key-989');

-- 989는 기준일 23 → 2026-09-10 시점 현재 주기 [08-23, 09-23), 라벨 202608. 예산·거래 없음
INSERT INTO user_settings (user_id, budget_anchor_day) VALUES (989, 23);

-- 991: 202609 확정 예산 (기준일 1 → 주기 [09-01, 10-01)), 의료(3)는 확정 0. 확정 합 780,000
INSERT INTO budgets (id, user_id, budget_month, status) VALUES (9003, 991, '202609', 'CONFIRMED');
INSERT INTO budget_envelopes (id, budget_id, envelope_id, proposed_amount, confirmed_amount) VALUES
 (9301, 9003, 1, 300000, 280000),
 (9302, 9003, 2, 100000, 100000),
 (9303, 9003, 3,  50000,      0),
 (9304, 9003, 4, 100000, 100000),
 (9305, 9003, 5, 100000, 100000),
 (9306, 9003, 6, 150000, 150000),
 (9307, 9003, 7,  50000,  50000);

-- 소비 합 298,000 → 남은 482,000 → 482000*100/780000 = 61.79 → 61
INSERT INTO transactions
 (id, user_id, source, tx_type, amount, tx_date, tx_time, subcategory_id, confirm_status, exclude_tag, adjusted_amount, status) VALUES
 (8101, 991, 'SEED', 'CARD', 148000, '2026-09-05', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 외식 → 남은 132,000 → 47%
 (8102, 991, 'SEED', 'CARD',  30000, '2026-09-06', '12:00:00', 301, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 의료(확정 0) → 남은 -30,000, 비율 null
 (8103, 991, 'SEED', 'CARD', 120000, '2026-09-07', '12:00:00', 201, 'CONFIRMED', 'NONE', NULL, 'NORMAL');   -- 교통 10만 초과 → 남은 -20,000 → -20%
