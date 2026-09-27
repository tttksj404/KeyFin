UPDATE user_settings
SET coach_persona = 'PLAIN'
WHERE coach_persona = 'ONSOON';

ALTER TABLE user_settings
	MODIFY COLUMN coach_persona VARCHAR(20) NOT NULL DEFAULT 'PLAIN'
	COMMENT '코치 말투 — PLAIN/DODO/ONSOON/JIBANG';

ALTER TABLE `fin_coin`
    ADD COLUMN `reward_grant_date` DATE GENERATED ALWAYS AS (
        CASE WHEN `reason_code` = 'PURCHASE' THEN NULL ELSE `grant_date` END
    ) STORED,
    ADD INDEX `idx_fin_coin_user_id` (`user_id`, `id`),
    DROP INDEX `uq_coin_grant`,
    ADD CONSTRAINT `uq_coin_grant` UNIQUE (`user_id`, `reward_grant_date`, `reason_code`);
