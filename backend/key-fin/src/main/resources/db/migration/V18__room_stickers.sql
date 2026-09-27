ALTER TABLE user_furnitures
    ADD COLUMN sticker_attached BOOLEAN NOT NULL DEFAULT FALSE,
    ADD CONSTRAINT chk_furniture_sticker CHECK (sticker_attached IN (FALSE, TRUE));

CREATE TABLE room_sticker_states (
    user_id BIGINT NOT NULL PRIMARY KEY,
    last_removed_date DATE NULL,
    CONSTRAINT fk_sticker_state_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE budget_sticker_applications (
    budget_id BIGINT NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    applied_at DATETIME NOT NULL,
    CONSTRAINT fk_sticker_application_budget FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
    CONSTRAINT fk_sticker_application_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_sticker_application_user (user_id)
);
