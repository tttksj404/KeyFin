INSERT INTO transactions
 (id, user_id, source, tx_type, merchant_name_raw, amount, tx_date, tx_time,
  subcategory_id, confirm_status, exclude_tag, adjusted_amount, status, memo) VALUES
 (8210, 987, 'SEED', 'CARD', '미확정 카드 결제', 8500, '2026-07-03', '13:00:00',
  NULL, 'PENDING', 'NONE', NULL, 'NORMAL', NULL),
 (8211, 987, 'SEED', 'DEPOSIT', '미확정 입금', 100000, '2026-07-04', '13:00:00',
  NULL, 'PENDING', 'NONE', NULL, 'NORMAL', NULL),
 (8212, 987, 'SEED', 'WITHDRAW', '취소된 미확정 출금', 12000, '2026-07-05', '13:00:00',
  NULL, 'PENDING', 'NONE', NULL, 'CANCELED', NULL),
 (8213, 986, 'SEED', 'CARD', '다른 사용자의 미확정 결제', 99000, '2026-07-06', '13:00:00',
  NULL, 'PENDING', 'NONE', NULL, 'NORMAL', NULL);
