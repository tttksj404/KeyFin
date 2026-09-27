INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (997, 'proposal-test@keyfin.io', 'x', '제안테스터', 'test-user-key-997'),
 (996, 'proposal-empty@keyfin.io', 'x', '무이력테스터', 'test-user-key-996'),
 (995, 'proposal-partial@keyfin.io', 'x', '부분이력테스터', 'test-user-key-995'),
 (994, 'proposal-fraction@keyfin.io', 'x', '부분달테스터', 'test-user-key-994'),
 (988, 'proposal-seeded@keyfin.io', 'x', '시딩공백테스터', 'test-user-key-988');

-- 994는 기준일 25 → 2026-09-10 시점 현재 주기 라벨 202608 ([08-25, 09-25)); 나머지는 설정 행 없음 → 기준일 1 → 202609
INSERT INTO user_settings (user_id, budget_anchor_day) VALUES (994, 25);

-- 테스트 고정 시계 = 2026-09-10. 집계 구간은 마지막 거래일 기준 3개월: 997은 마지막 9/1 → [2026-06-02, 2026-09-02), 구간 92일
INSERT INTO transactions
 (id, user_id, source, tx_type, amount, tx_date, tx_time, subcategory_id, confirm_status, exclude_tag, adjusted_amount, status) VALUES
 (8001, 997, 'SEED', 'CARD', 100000, '2026-06-10', '12:00:00', 101, 'AUTO',      'NONE', NULL, 'NORMAL'),   -- 외식
 (8002, 997, 'SEED', 'CARD', 120000, '2026-07-10', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 외식
 (8003, 997, 'SEED', 'CARD',  80000, '2026-08-10', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 외식
 (8004, 997, 'SEED', 'CARD', 100000, '2026-07-15', '12:00:00', 201, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 교통 10만 → ×30/92 = 32,608 → 33,000
 (8005, 997, 'SEED', 'CARD',  50000, '2026-05-31', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 구간 이전 → 집계 제외 (최초 거래일로는 사용)
 (8006, 997, 'SEED', 'CARD',  70000, '2026-09-01', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 외식 → 합 37만 → ×30/92 = 120,652 → 121,000
 (8007, 995, 'SEED', 'CARD',  90000, '2026-08-15', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 커버 26일 → 하한 30일 → 평균 9만 (확대 없음)
 (8008, 994, 'SEED', 'CARD', 100000, '2026-06-25', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 최초 거래 6/25 → 커버 77일
 (8009, 994, 'SEED', 'CARD', 130000, '2026-08-01', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 마지막 8/1 → 구간 [5/2, 8/2), 커버 6/25~8/1 = 38일 → 합 23만 ×30/38 = 181,578 → 182,000
 (8010, 988, 'SEED', 'CARD', 100000, '2026-06-01', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),   -- 시딩 데이터 6/1~8/31, 오늘 9/10 (공백 10일)
 (8011, 988, 'SEED', 'CARD', 100000, '2026-07-15', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL'),
 (8012, 988, 'SEED', 'CARD', 100000, '2026-08-31', '12:00:00', 101, 'CONFIRMED', 'NONE', NULL, 'NORMAL');   -- 마지막 8/31 → 구간 [6/1, 9/1) 92일, 합 30만 ×30/92 = 97,826 → 98,000 (오늘 기준이면 6/1 제외·65,217)
