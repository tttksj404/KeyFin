INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (999, 'balance-test@keyfin.io', 'x', '잔액테스터', 'test-user-key-999'),
 (998, 'balance-other@keyfin.io', 'x', '옆사람', 'test-user-key-998');

INSERT INTO budgets (id, user_id, budget_month, status) VALUES
 (900, 999, '202609', 'CONFIRMED');

-- 봉투 1(외식) 30만 확정, 2(교통비) 10만 확정, 3(의료·건강) 미승인(confirmed NULL)
INSERT INTO budget_envelopes (id, budget_id, envelope_id, proposed_amount, confirmed_amount) VALUES
 (901, 900, 1, 300000, 300000),
 (902, 900, 2, 100000, 100000),
 (903, 900, 3,  50000, NULL);

-- 세분류: 101=음식점(봉투1), 201=대중교통(봉투2) — V1 기준 데이터 사용
INSERT INTO transactions
 (id, user_id, source, tx_type, amount, tx_date, tx_time, subcategory_id, confirm_status, exclude_tag, adjusted_amount, status) VALUES
 (9001, 999, 'SEED', 'CARD',      10000, '2026-09-05', '12:00:00', 101,  'AUTO',      'NONE',          NULL,  'NORMAL'),   -- 전액 차감 +10000
 (9002, 999, 'SEED', 'WITHDRAW',  50000, '2026-09-06', '19:00:00', 101,  'CONFIRMED', 'DUTCH',         12500, 'NORMAL'),   -- 부분 차감 +12500
 (9003, 999, 'SEED', 'CARD',       7000, '2026-09-07', '12:00:00', 101,  'PENDING',   'NONE',          NULL,  'NORMAL'),   -- 미확정 → 제외
 (9004, 999, 'SEED', 'CARD',       8000, '2026-09-08', '12:00:00', 101,  'CONFIRMED', 'NONE',          NULL,  'CANCELED'), -- 취소 → 제외
 (9005, 999, 'SEED', 'TRANSFER',  20000, '2026-09-09', '12:00:00', 101,  'CONFIRMED', 'SELF_TRANSFER', NULL,  'NORMAL'),   -- 내 계좌 이동 → 제외
 (9006, 999, 'SEED', 'DEPOSIT',  300000, '2026-09-10', '09:00:00', NULL, 'AUTO',      'NONE',          NULL,  'NORMAL'),   -- 입금 → 제외
 (9007, 999, 'SEED', 'CARD',       1500, '2026-10-01', '12:00:00', 201,  'CONFIRMED', 'NONE',          NULL,  'NORMAL'),   -- 다음 달 → 제외
 (9008, 999, 'SEED', 'CARD',       1400, '2026-09-10', '12:00:00', 201,  'CONFIRMED', 'NONE',          NULL,  'NORMAL'),   -- 봉투2 +1400
 (9009, 998, 'SEED', 'CARD',       9999, '2026-09-11', '12:00:00', 101,  'CONFIRMED', 'NONE',          NULL,  'NORMAL'),   -- 남의 거래 → 제외
 (9010, 999, 'SEED', 'DEPOSIT',    3000, '2026-09-12', '10:00:00', 101,  'AUTO',      'RESTORE',       NULL,  'NORMAL');   -- 환급 입금 → 봉투1 복원 -3000
