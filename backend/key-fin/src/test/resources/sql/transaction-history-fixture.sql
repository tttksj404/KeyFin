INSERT INTO users (id, email, password, name, fin_user_key) VALUES
 (987, 'transaction-history@keyfin.io', 'x', '거래조회테스터', 'test-user-key-987'),
 (986, 'other-transaction@keyfin.io', 'x', '다른사용자', 'test-user-key-986');

INSERT INTO transactions
 (id, user_id, source, tx_type, merchant_name_raw, amount, tx_date, tx_time,
  subcategory_id, confirm_status, exclude_tag, adjusted_amount, status, memo) VALUES
 (8201, 987, 'SEED', 'CARD', '메가커피 역삼점', 4500, '2026-09-08', '14:21:00',
  102, 'AUTO', 'NONE', NULL, 'NORMAL', NULL),
 (8202, 987, 'SEED', 'WITHDRAW', '공동 식사', 30000, '2026-09-09', '12:00:00',
  101, 'CONFIRMED', 'DUTCH', 15000, 'NORMAL', '정산 예정'),
 (8203, 987, 'SEED', 'CARD', '취소된 결제', 12000, '2026-09-10', '10:00:00',
  401, 'CONFIRMED', 'NONE', NULL, 'CANCELED', NULL),
 (8190, 987, 'SEED', 'CARD', 'ID와 날짜 순서가 다른 결제', 7000, '2026-09-12', '09:00:00',
  201, 'AUTO', 'NONE', NULL, 'NORMAL', NULL),
 (8204, 987, 'SEED', 'CARD', '전월 결제', 5000, '2026-08-31', '20:00:00',
  102, 'AUTO', 'NONE', NULL, 'NORMAL', NULL),
 (8299, 986, 'SEED', 'CARD', '다른 사용자 결제', 99000, '2026-09-11', '09:00:00',
  102, 'AUTO', 'NONE', NULL, 'NORMAL', NULL);
