ALTER TABLE `cards`
	MODIFY COLUMN `card_name` VARCHAR(100) NOT NULL COMMENT '카드명 — 금융망 cardName',
	ADD CONSTRAINT `uq_cards` UNIQUE (`user_id`, `fin_card_no_enc`);
