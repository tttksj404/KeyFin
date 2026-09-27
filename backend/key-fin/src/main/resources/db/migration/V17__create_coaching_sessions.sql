-- 사용자당 코칭 서버 세션 하나. 대화 본문은 코칭 서버가 보관하고 여기에는 세션 포인터만 둔다(FR-AI-04).
CREATE TABLE `coaching_sessions` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID — users',
	`session_id`	VARCHAR(64)	NOT NULL	COMMENT '코칭 서버 세션 ID',
	`expires_at`	DATETIME	NOT NULL	COMMENT '코칭 서버가 정한 만료 시각',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	`updated_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP	COMMENT '수정 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_coaching_session_user` UNIQUE (`user_id`),
	CONSTRAINT `fk_coaching_session_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) COMMENT='코칭 대화 세션';
