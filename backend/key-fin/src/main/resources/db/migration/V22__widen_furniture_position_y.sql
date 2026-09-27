-- The mobile room scene changed from 327x404 to 327x586 (2026-09-18). Widen position_y to match.
-- Existing rows are all within 0..404, so they already satisfy the new constraint. position_x (0..327) is unchanged.
ALTER TABLE user_furnitures
    DROP CHECK chk_uf_position_y,
    ADD CONSTRAINT chk_uf_position_y CHECK (position_y IS NULL OR position_y BETWEEN 0 AND 586);
