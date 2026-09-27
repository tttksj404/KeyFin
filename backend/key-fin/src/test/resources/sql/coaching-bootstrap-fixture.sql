-- FDT 어댑터 검증용. 사용자 1명, 계좌 2·카드 2(하나는 출금 요일 미기록), 청구서 3, 고정지출 4, 예산 1주기.
-- 거래는 태그·유형 조합을 한 건씩 둬 변환 규칙을 전부 밟게 한다.

INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (970, 'fdt@keyfin.io', 'x', '어댑터테스터', 'test-user-key-970');

INSERT INTO user_settings (user_id, budget_anchor_day) VALUES (970, 1);

INSERT INTO accounts (id, user_id, fin_account_no, bank_code, bank_name, alias, balance, balance_updated_at, is_managed, is_income) VALUES
 (9700, 970, '0019700000000001', '004', '국민은행', '생활비', 5458220, '2026-09-10 09:00:00', TRUE, TRUE),
 (9701, 970, '0019700000000002', '081', '하나은행', '비상금', 316350, '2026-09-10 09:00:00', TRUE, FALSE),
 (9702, 970, '0019700000000003', '088', '신한은행', '해지계좌', 999999, '2026-09-10 09:00:00', FALSE, FALSE);

-- 9710: 출금 요일 3=수 / 9711: 출금 요일 1=월 / 9712: 출금 요일 미기록 → 스냅샷에서 빠져야 함
INSERT INTO cards (id, user_id, fin_card_no_enc, cvc, issuer_code, card_name, withdrawal_account_id, withdrawal_weekday, is_managed) VALUES
 (9710, 970, '1001970100000001', '111', '1001', '삼성카드', 9700, 3, TRUE),
 (9711, 970, '1001970100000002', '222', '1001', '하나카드', 9701, 1, TRUE),
 (9712, 970, '1001970100000003', '333', '1001', '요일미상카드', 9700, NULL, TRUE);

-- 9720/9721 미납(카드 9710 합 500000), 9722 결제완료(제외), 9723 카드 9712 미납(카드가 빠지므로 함께 제외)
INSERT INTO card_billings (id, card_id, billing_date, total_amount, status, paid_at) VALUES
 (9720, 9710, '2026-09-07', 300000, 'UNPAID', NULL),
 (9721, 9710, '2026-08-31', 200000, 'UNPAID', NULL),
 (9722, 9711, '2026-08-31', 150000, 'PAID',   '2026-09-01 16:00:00'),
 (9723, 9712, '2026-09-07', 111111, 'UNPAID', NULL);

-- 월세(주거) · 관리비(공과금) · 학자금(대출, fixed_group 없음) · 카드대금(청구서와 중복 → 제외)
INSERT INTO fixed_expenses (id, user_id, name, expense_type, amount, is_variable, payment_day, withdrawal_account_id, fin_subscription_id, active) VALUES
 (9730, 970, '월세',       'RENT',         750000, FALSE,  5, 9700, NULL, TRUE),
 (9731, 970, '관리비',     'UTILITY',      115000, TRUE,  25, 9700, NULL, TRUE),
 (9732, 970, '학자금 상환', 'LOAN',         200000, FALSE, 15, 9700, NULL, TRUE),
 (9733, 970, '삼성카드 대금','CARD_BILL',   400000, FALSE, 10, 9700, NULL, TRUE);

INSERT INTO budgets (id, user_id, budget_month, status, emergency_amount) VALUES
 (9740, 970, '202609', 'CONFIRMED', 300000);

-- 외식 확정 280000 / 교통비 확정 90000 / 쇼핑은 제안만(확정 없음) → budgets 에서 빠져야 함
INSERT INTO budget_envelopes (id, budget_id, envelope_id, proposed_amount, confirmed_amount) VALUES
 (9741, 9740, 1, 260000, 280000),
 (9742, 9740, 2,  80000,  90000),
 (9743, 9740, 5, 120000,   NULL);

INSERT INTO transactions
 (id, user_id, source, fin_tx_unique_no, tx_type, account_id, card_id, merchant_id, merchant_name_raw, amount, tx_date, tx_time, subcategory_id, confirm_status, exclude_tag, adjusted_amount, status) VALUES
 -- 카드 · 매핑된 가맹점 · 카페
 (9750, 970, 'LIVE', '20260902000000000001', 'CARD',    NULL, 9710,   26, '메가MGC커피 선릉역점',  4500, '2026-09-02', '08:30:00',  102, 'AUTO',      'NONE',      NULL, 'NORMAL'),
 -- 카드 · 미매핑 가맹점 · 세분류 없음
 (9751, 970, 'LIVE', '20260903000000000002', 'CARD',    NULL, 9710, NULL, '무명김밥집',           7000, '2026-09-03', '12:10:00', NULL, 'PENDING',   'NONE',      NULL, 'NORMAL'),
 -- 카드 · 더치페이 · 실제 결제액 100000, 내 몫 40000
 (9752, 970, 'LIVE', '20260904000000000003', 'CARD',    NULL, 9710,   20, '버거킹 신촌점',      100000, '2026-09-04', '19:00:00',  101, 'CONFIRMED', 'DUTCH',    40000, 'NORMAL'),
 -- 카드 · 마트 (세분류 602)
 (9753, 970, 'LIVE', '20260905000000000004', 'CARD',    NULL, 9710,   52, '이마트 왕십리점',     38000, '2026-09-05', '18:00:00',  602, 'AUTO',      'NONE',      NULL, 'NORMAL'),
 -- 계좌 · 월세 송금 (TRANSFER + NONE → TRANSFER_OUT)
 (9754, 970, 'LIVE', '20260905000000000005', 'TRANSFER', 9700, NULL, NULL, '김정민',            750000, '2026-09-05', '09:00:00', NULL, 'PENDING',   'NONE',      NULL, 'NORMAL'),
 -- 계좌 · 본인 계좌 이동 (TRANSFER + SELF_TRANSFER → TRANSFER)
 (9755, 970, 'LIVE', '20260906000000000006', 'TRANSFER', 9700, NULL, NULL, '정재원',            200000, '2026-09-06', '10:00:00', NULL, 'CONFIRMED', 'SELF_TRANSFER', NULL, 'NORMAL'),
 -- 계좌 · 환급 입금 (RESTORE → DEPOSIT + NONE)
 (9756, 970, 'LIVE', '20260907000000000007', 'DEPOSIT',  9700, NULL, NULL, '정산 수령',          30000, '2026-09-07', '11:00:00',  101, 'CONFIRMED', 'RESTORE',   NULL, 'NORMAL'),
 -- 계좌 · 시딩 이월 마커 (CARRYOVER → 원장에서 제외)
 (9757, 970, 'SEED', '20260601000000000008', 'DEPOSIT',  9700, NULL, NULL, '초기 잔액 설정(시딩)', 2600000, '2026-06-01', '00:00:00', NULL, 'CONFIRMED', 'CARRYOVER', NULL, 'NORMAL'),
 -- 계좌 · 비상금 사용
 (9758, 970, 'LIVE', '20260908000000000009', 'WITHDRAW', 9701, NULL, NULL, 'ATM 출금',           50000, '2026-09-08', '14:00:00',  703, 'CONFIRMED', 'EMERGENCY', NULL, 'NORMAL'),
 -- 카드 · 취소된 거래
 (9759, 970, 'LIVE', '20260909000000000010', 'CARD',    NULL, 9710,   26, '메가MGC커피 선릉역점',  5000, '2026-09-09', '15:00:00',  102, 'AUTO',      'NONE',      NULL, 'CANCELED');
