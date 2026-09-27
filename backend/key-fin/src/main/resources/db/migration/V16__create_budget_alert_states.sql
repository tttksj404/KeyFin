-- 봉투별 마지막 알림 단계. 현재 단계가 이보다 심각해졌을 때만 알림을 만든다(FR-BGT-05).
-- 예산 주기가 바뀌면 새 budgets 행이 생기므로 단계도 자연히 초기화된다.
CREATE TABLE `budget_alert_states` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`budget_id`	BIGINT	NOT NULL	COMMENT '예산 ID — budgets',
	`envelope_id`	INT	NOT NULL	COMMENT '봉투 ID — envelopes',
	`last_alert_level`	VARCHAR(20)	NOT NULL	COMMENT '마지막으로 알린 단계 — NONE/REMAINING_50/REMAINING_20/REMAINING_5/EXCEEDED',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	`updated_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP	COMMENT '수정 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_budget_alert_state` UNIQUE (`budget_id`, `envelope_id`),
	CONSTRAINT `fk_budget_alert_state_budget` FOREIGN KEY (`budget_id`) REFERENCES `budgets`(`id`),
	CONSTRAINT `fk_budget_alert_state_envelope` FOREIGN KEY (`envelope_id`) REFERENCES `envelopes`(`id`)
) COMMENT='봉투 잔액 구간 알림 상태';
