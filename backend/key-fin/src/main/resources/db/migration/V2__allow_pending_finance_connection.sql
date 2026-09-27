ALTER TABLE `users`
	MODIFY COLUMN `fin_user_key` VARCHAR(60) NULL
		COMMENT '금융망 사용자 키 — 금융망 연결 전 NULL';
