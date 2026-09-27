DELETE FROM notifications WHERE user_id IN (986, 987, 988);
DELETE FROM audit_logs WHERE user_id IN (986, 987, 988);
DELETE FROM prepare_transfers WHERE user_id IN (986, 987, 988);
DELETE FROM card_billings WHERE card_id = 9603;
DELETE FROM cards WHERE user_id IN (986, 987, 988);
DELETE FROM fixed_expenses WHERE user_id IN (986, 987, 988);
DELETE FROM user_settings WHERE user_id IN (986, 987, 988);
DELETE FROM accounts WHERE user_id IN (986, 987, 988);
DELETE FROM users WHERE id IN (986, 987, 988);
