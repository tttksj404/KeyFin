CREATE TABLE `users` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`email`	VARCHAR(100)	NOT NULL	COMMENT '이메일(로그인 ID)',
	`password`	VARCHAR(255)	NOT NULL	COMMENT '비밀번호 해시',
	`name`	VARCHAR(30)	NOT NULL	COMMENT '이름',
	`fin_user_key`	VARCHAR(60)	NOT NULL	COMMENT '금융망 사용자 키 — 금융망 userKey',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	`updated_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP	COMMENT '수정 시각',
	`deleted_at`	DATETIME	NULL	COMMENT '탈퇴 시각(소프트 삭제)',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_users_email` UNIQUE (`email`)
) COMMENT='사용자';

CREATE TABLE `user_profiles` (
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID — users 1:1',
	`birth_date`	DATE	NULL	COMMENT '생년월일 — 정책 연령 판정용 (선택 입력)',
	`region_code`	VARCHAR(10)	NULL	COMMENT '지역 코드 — 시·군·구 행정코드 — 상세 주소 미수집',
	`employment_status`	VARCHAR(20)	NULL	COMMENT '고용 상태 — STUDENT/JOB_SEEKER/EMPLOYED/FREELANCER',
	`income_band`	VARCHAR(20)	NULL	COMMENT '소득 구간 (정책 조건용, 선택)',
	`updated_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP	COMMENT '수정 시각',
	PRIMARY KEY (`user_id`),
	CONSTRAINT `fk_profile_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) COMMENT='사용자 프로필';

CREATE TABLE `user_settings` (
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID — users 1:1',
	`coach_persona`	VARCHAR(20)	NOT NULL	DEFAULT 'ONSOON'	COMMENT '코치 말투 — DODO/ONSOON/JIBANG',
	`noti_coaching`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '코칭 알림 수신',
	`noti_budget_alert`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '예산 알림 수신',
	`noti_transfer`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '이체 알림 수신',
	`noti_cleanup`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '정리 세션 알림 수신',
	`quiet_hours_start`	TIME	NULL	COMMENT '방해금지 시작 — 방해 금지 시작',
	`quiet_hours_end`	TIME	NULL	COMMENT '방해금지 종료',
	`transfer_consent`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '자동 이체 동의 — 결제 준비 이체 동의 (opt-in)',
	`transfer_limit_once`	BIGINT	NULL	COMMENT '1회 이체 한도 — NULL=미설정(무제한, 기본). 사용자 opt-in 설정',
	`transfer_limit_daily`	BIGINT	NULL	COMMENT '1일 이체 한도 — NULL=미설정(무제한, 기본). 사용자 opt-in 설정',
	`updated_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP	COMMENT '수정 시각',
	PRIMARY KEY (`user_id`),
	CONSTRAINT `fk_settings_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) COMMENT='사용자 설정';

CREATE TABLE `accounts` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`fin_account_no`	VARCHAR(16)	NOT NULL	COMMENT '금융망 계좌번호',
	`bank_code`	VARCHAR(3)	NOT NULL	COMMENT '은행 코드',
	`alias`	VARCHAR(30)	NULL	COMMENT '계좌 별칭',
	`is_managed`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '관리 대상 여부 — 관리 대상 opt-in',
	`is_income`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '수입 계좌 여부',
	`linked_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '연결 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_accounts` UNIQUE (`user_id`,`fin_account_no`),
	CONSTRAINT `fk_accounts_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) COMMENT='연결 계좌';

CREATE TABLE `cards` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`fin_card_no_enc`	VARCHAR(255)	NOT NULL	COMMENT '카드번호 — 금융망 목록 조회 응답값 (교육용 더미)',
	`cvc`	CHAR(3)	NOT NULL	COMMENT 'CVC — 금융망 목록 조회 응답값 (교육용 더미). 결제 내역·청구서 조회 API 호출에 사용 (팀 결정 2026.9.7)',
	`issuer_code`	VARCHAR(4)	NOT NULL	COMMENT '카드사 코드',
	`card_name`	VARCHAR(20)	NOT NULL	COMMENT '카드명',
	`withdrawal_account_id`	BIGINT	NULL	COMMENT '청구 출금 계좌 ID — 청구 출금 계좌',
	`is_managed`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '관리 대상 여부',
	`linked_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '연결 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `fk_cards_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
	CONSTRAINT `fk_cards_account` FOREIGN KEY (`withdrawal_account_id`) REFERENCES `accounts`(`id`)
) COMMENT='연결 카드';

CREATE TABLE `envelopes` (
	`id`	INT	NOT NULL	COMMENT '고유 ID',
	`name`	VARCHAR(20)	NOT NULL	COMMENT '봉투명 — 봉투 7종',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_envelopes_name` UNIQUE (`name`)
) COMMENT='예산 봉투';

CREATE TABLE `subcategories` (
	`id`	INT	NOT NULL	COMMENT '고유 ID',
	`envelope_id`	INT	NOT NULL	COMMENT '소속 봉투 ID',
	`name`	VARCHAR(20)	NOT NULL	COMMENT '세분류명 — KeyFin 세분류 22종',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_subcat_name` UNIQUE (`name`),
	CONSTRAINT `fk_subcat_envelope` FOREIGN KEY (`envelope_id`) REFERENCES `envelopes`(`id`)
) COMMENT='소비 세분류';

CREATE TABLE `merchants` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`fin_merchant_id`	BIGINT	NULL	COMMENT '금융망 가맹점 ID — 금융망 merchantId (등록 후 채움)',
	`name`	VARCHAR(100)	NOT NULL	COMMENT '가맹점명',
	`subcategory_id`	INT	NOT NULL	COMMENT '세분류 ID — 분류의 1차 진실 (FR-TXN-10)',
	`fin_category_id`	VARCHAR(40)	NULL	COMMENT '금융망 업종 ID — 금융망 업종 (참고용)',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_merchant_fin` UNIQUE (`fin_merchant_id`),
	CONSTRAINT `fk_merchants_subcat` FOREIGN KEY (`subcategory_id`) REFERENCES `subcategories`(`id`)
) COMMENT='가맹점';

CREATE TABLE `transactions` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`source`	VARCHAR(10)	NOT NULL	COMMENT '데이터 출처 — SEED / LIVE (실행·대사·청구 계산은 LIVE만)',
	`fin_tx_unique_no`	VARCHAR(20)	NULL	COMMENT '금융망 거래번호 — 금융망 거래고유번호 (SEED는 NULL)',
	`tx_type`	VARCHAR(20)	NOT NULL	COMMENT '거래 유형 — CARD/DEPOSIT/WITHDRAW/TRANSFER',
	`account_id`	BIGINT	NULL	COMMENT '계좌 ID',
	`card_id`	BIGINT	NULL	COMMENT '카드 ID',
	`merchant_id`	BIGINT	NULL	COMMENT '가맹점 ID',
	`merchant_name_raw`	VARCHAR(100)	NULL	COMMENT '가맹점명 원문',
	`amount`	BIGINT	NOT NULL	COMMENT '거래 금액 — 원 단위',
	`tx_date`	DATE	NOT NULL	COMMENT '거래 일자',
	`tx_time`	TIME	NOT NULL	COMMENT '거래 시각',
	`subcategory_id`	INT	NULL	COMMENT '세분류 ID(분류 결과) — 분류 결과',
	`confirm_status`	VARCHAR(20)	NOT NULL	DEFAULT 'PENDING'	COMMENT '분류 확정 상태 — AUTO/PENDING/CONFIRMED (입금 DEPOSIT은 AUTO 고정 — 분류·질문 제외)',
	`exclude_tag`	VARCHAR(20)	NOT NULL	DEFAULT 'NONE'	COMMENT '예산 제외 태그 — NONE(전액 차감)/DUTCH(부분 차감)/SELF_TRANSFER/EMERGENCY/CARRYOVER',
	`adjusted_amount`	BIGINT	NULL	COMMENT '차감 인정액 — DUTCH(더치페이) 시 내 몫만 차감 (0~amount, 직접 입력 또는 인원수 1/n 계산). DUTCH 외 태그는 NULL',
	`status`	VARCHAR(20)	NOT NULL	DEFAULT 'NORMAL'	COMMENT '거래 상태 — NORMAL/CANCELED',
	`memo`	VARCHAR(255)	NULL	COMMENT '메모',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_tx_fin_no` UNIQUE (`user_id`,`fin_tx_unique_no`),
	CONSTRAINT `fk_tx_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
	CONSTRAINT `fk_tx_account` FOREIGN KEY (`account_id`) REFERENCES `accounts`(`id`),
	CONSTRAINT `fk_tx_card` FOREIGN KEY (`card_id`) REFERENCES `cards`(`id`),
	CONSTRAINT `fk_tx_merchant` FOREIGN KEY (`merchant_id`) REFERENCES `merchants`(`id`),
	CONSTRAINT `fk_tx_subcat` FOREIGN KEY (`subcategory_id`) REFERENCES `subcategories`(`id`),
	INDEX `idx_tx_user_date` (`user_id`,`tx_date`),
	INDEX `idx_tx_pending` (`user_id`,`confirm_status`)
) COMMENT='거래 원장';

CREATE TABLE `card_billings` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`card_id`	BIGINT	NOT NULL	COMMENT '카드 ID',
	`billing_date`	DATE	NOT NULL	COMMENT '청구서 발행일 — 주 단위 발행일 (월요일)',
	`total_amount`	BIGINT	NOT NULL	COMMENT '청구 금액',
	`status`	VARCHAR(20)	NOT NULL	DEFAULT 'UNPAID'	COMMENT '결제 상태 — UNPAID/PAID',
	`paid_at`	DATETIME	NULL	COMMENT '납입 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_billing` UNIQUE (`card_id`,`billing_date`),
	CONSTRAINT `fk_billing_card` FOREIGN KEY (`card_id`) REFERENCES `cards`(`id`)
) COMMENT='카드 청구서';

CREATE TABLE `budgets` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`budget_month`	CHAR(6)	NOT NULL	COMMENT '예산 월 — YYYYMM',
	`status`	VARCHAR(20)	NOT NULL	DEFAULT 'PROPOSED'	COMMENT '예산 상태 — PROPOSED/CONFIRMED',
	`emergency_amount`	BIGINT	NOT NULL	DEFAULT 0	COMMENT '비상금 — 가상 풀 월 금액, 0=미설정. 차감은 거래 exclude_tag=EMERGENCY로 (FR-BGT-09)',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_budget` UNIQUE (`user_id`,`budget_month`),
	CONSTRAINT `fk_budget_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) COMMENT='월 예산';

CREATE TABLE `budget_envelopes` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`budget_id`	BIGINT	NOT NULL	COMMENT '예산 ID',
	`envelope_id`	INT	NOT NULL	COMMENT '봉투 ID',
	`proposed_amount`	BIGINT	NOT NULL	COMMENT 'AI 제안액',
	`confirmed_amount`	BIGINT	NULL	COMMENT '사용자 확정액 (승인 전 NULL)',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_be` UNIQUE (`budget_id`,`envelope_id`),
	CONSTRAINT `fk_be_budget` FOREIGN KEY (`budget_id`) REFERENCES `budgets`(`id`),
	CONSTRAINT `fk_be_envelope` FOREIGN KEY (`envelope_id`) REFERENCES `envelopes`(`id`)
) COMMENT='봉투별 예산';

CREATE TABLE `fixed_expenses` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`name`	VARCHAR(50)	NOT NULL	COMMENT '지출명',
	`expense_type`	VARCHAR(20)	NOT NULL	COMMENT '지출 유형 — RENT/SUBSCRIPTION/CARD_BILL/LOAN/UTILITY',
	`amount`	BIGINT	NULL	COMMENT '금액 — 고정형은 확정액, 변동형 수동 등록은 예상액 입력. 자동 감지 CARD_BILL은 NULL(엔진 계산)',
	`is_variable`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '변동형 여부',
	`payment_day`	INT	NOT NULL	COMMENT '출금일 — 1~31',
	`withdrawal_account_id`	BIGINT	NOT NULL	COMMENT '출금 계좌 ID',
	`fin_subscription_id`	VARCHAR(30)	NULL	COMMENT '금융망 정기결제 ID',
	`active`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '활성 여부',
	PRIMARY KEY (`id`),
	CONSTRAINT `fk_fe_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
	CONSTRAINT `fk_fe_account` FOREIGN KEY (`withdrawal_account_id`) REFERENCES `accounts`(`id`)
) COMMENT='정기 지출';

CREATE TABLE `prepare_transfers` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`fixed_expense_id`	BIGINT	NULL	COMMENT '대상 고정지출 ID',
	`scheduled_date`	DATE	NOT NULL	COMMENT '실행 예정일',
	`required_amount`	BIGINT	NOT NULL	COMMENT '필요 금액',
	`from_account_id`	BIGINT	NOT NULL	COMMENT '출금 계좌 ID',
	`to_account_id`	BIGINT	NOT NULL	COMMENT '입금 계좌 ID',
	`status`	VARCHAR(20)	NOT NULL	DEFAULT 'PROPOSED'	COMMENT '이체 상태 — PROPOSED/APPROVED/EXECUTED/FAILED/CANCELED',
	`institution_tx_no`	VARCHAR(20)	NULL	COMMENT '기관거래고유번호(멱등 키) — 금융망 멱등 키 (H1007)',
	`executed_at`	DATETIME	NULL	COMMENT '실행 시각',
	`fail_reason`	VARCHAR(255)	NULL	COMMENT '실패 사유',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_pt_txno` UNIQUE (`institution_tx_no`),
	CONSTRAINT `fk_pt_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
	CONSTRAINT `fk_pt_fe` FOREIGN KEY (`fixed_expense_id`) REFERENCES `fixed_expenses`(`id`),
	CONSTRAINT `fk_pt_from` FOREIGN KEY (`from_account_id`) REFERENCES `accounts`(`id`),
	CONSTRAINT `fk_pt_to` FOREIGN KEY (`to_account_id`) REFERENCES `accounts`(`id`)
) COMMENT='결제 준비 이체';

CREATE TABLE `audit_logs` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`action`	VARCHAR(20)	NOT NULL	COMMENT '행동 유형 — EXECUTE/HOLD/FAIL/CANCEL',
	`target_type`	VARCHAR(30)	NOT NULL	COMMENT '대상 유형',
	`target_id`	VARCHAR(30)	NOT NULL	COMMENT '대상 ID',
	`basis`	TEXT	NULL	COMMENT '판단 근거 — 적용 규칙·입력값·산출 근거',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) COMMENT='감사 로그';

CREATE TABLE `fin_coin` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`delta`	INT	NOT NULL	COMMENT '코인 증감량 — 적립 양수 / 사용 음수',
	`balance_after`	INT	NOT NULL	COMMENT '거래 후 잔액 — 직전 행 잔액+delta. 삽입 전 사용자 단위 잠금 필수, 정정은 삭제 금지·역분개 행으로만',
	`reason_code`	VARCHAR(20)	NOT NULL	COMMENT '지급 사유 — ATTEND/CONFIRM_ALL/WEEKLY/MONTHLY/PURCHASE',
	`grant_date`	DATE	NOT NULL	COMMENT '지급 기준일 — 중복 지급 방지 키',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	`ref_id`	VARCHAR(30)	NULL	COMMENT '참조 ID',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_coin_grant` UNIQUE (`user_id`,`grant_date`,`reason_code`),
	CONSTRAINT `fk_coin_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) COMMENT='코인 원장';

CREATE TABLE `items` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`slot_type`	VARCHAR(20)	NOT NULL	COMMENT '장착 자리: HAIR/OUTFIT/FACE(캐릭터) · WALLPAPER/FLOOR/CLOCK/SOFA/TABLE/DECO(방)',
	`name`	VARCHAR(50)	NOT NULL	COMMENT '아이템명',
	`price`	INT	NOT NULL	COMMENT '가격(코인)',
	`asset_key`	VARCHAR(100)	NOT NULL	COMMENT '리소스 키',
	`theme_code`	VARCHAR(30)	NULL	COMMENT '테마 코드 — 이벤트·테마 묶음 (예: AUTUMN_2026). NULL = 상시 아이템',
	PRIMARY KEY (`id`)
) COMMENT='꾸미기 아이템';

CREATE TABLE `user_items` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`item_id`	BIGINT	NOT NULL	COMMENT '아이템 ID',
	`equipped_slot`	VARCHAR(20)	NULL	COMMENT '장착 자리(NULL=미장착) — 장착 자리(HAIR/SOFA…). NULL=미장착. items.slot_type과 일치해야(앱 검증)',
	`acquired_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '획득 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `uq_ui` UNIQUE (`user_id`,`item_id`),
	-- 자리당 1개 장착 강제: NULL(미장착)은 중복 허용, 같은 자리 장착 행은 사용자당 1개
	CONSTRAINT `uq_ui_slot` UNIQUE (`user_id`,`equipped_slot`),
	CONSTRAINT `fk_ui_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
	CONSTRAINT `fk_ui_item` FOREIGN KEY (`item_id`) REFERENCES `items`(`id`)
) COMMENT='보유 아이템';

CREATE TABLE `coaching_logs` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`transaction_id`	BIGINT	NULL	COMMENT '거래 ID',
	`trigger_type`	VARCHAR(10)	NOT NULL	COMMENT '발동 경로 — RULE/LLM',
	`persona`	VARCHAR(20)	NOT NULL	COMMENT '페르소나',
	`message`	TEXT	NOT NULL	COMMENT '멘트 내용',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `fk_coach_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
	CONSTRAINT `fk_coach_tx` FOREIGN KEY (`transaction_id`) REFERENCES `transactions`(`id`)
) COMMENT='코칭 기록';

CREATE TABLE `notifications` (
	`id`	BIGINT	NOT NULL	AUTO_INCREMENT	COMMENT '고유 ID',
	`user_id`	BIGINT	NOT NULL	COMMENT '사용자 ID',
	`noti_type`	VARCHAR(30)	NOT NULL	COMMENT '알림 유형 — COACHING/BUDGET_ALERT/TRANSFER_REQUEST/CLEANUP/WARNING',
	`title`	VARCHAR(100)	NOT NULL	COMMENT '제목',
	`body`	TEXT	NULL	COMMENT '본문',
	`ref_id`	VARCHAR(30)	NULL	COMMENT '참조 ID',
	`requires_action`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '처리 필요 여부',
	`is_read`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '읽음 여부',
	`created_at`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	PRIMARY KEY (`id`),
	CONSTRAINT `fk_noti_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
	INDEX `idx_noti_user` (`user_id`,`is_read`,`created_at`)
) COMMENT='알림함';

-- 기준 데이터 (봉투 7종 · 세분류 22종)
INSERT INTO `envelopes` (`id`,`name`) VALUES
 (1,'외식'),(2,'교통비'),(3,'의료·건강'),(4,'취미·여가'),(5,'쇼핑'),(6,'편의점·마트·잡화'),(7,'기타');

INSERT INTO `subcategories` (`id`,`envelope_id`,`name`) VALUES
 (101,1,'음식점'),(102,1,'카페'),(103,1,'배달'),(104,1,'주점'),
 (201,2,'대중교통'),(202,2,'택시'),(203,2,'주유'),
 (301,3,'병원·약국'),(302,3,'운동·헬스'),
 (401,4,'영화·공연·전시'),(402,4,'스포츠 관람'),(403,4,'게임·콘텐츠'),(404,4,'여행·숙박'),
 (501,5,'패션·잡화'),(502,5,'뷰티'),(503,5,'온라인 쇼핑'),
 (601,6,'편의점'),(602,6,'마트'),(603,6,'생활용품'),
 (701,7,'교육'),(702,7,'해외 결제'),(703,7,'경조사·기타');
