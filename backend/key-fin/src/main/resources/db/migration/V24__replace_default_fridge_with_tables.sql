-- Preserve catalogue IDs and ownership when promoting the two original tables.
-- Existing migrations remain unchanged for databases already on V23.
ALTER TABLE items
    DROP CHECK chk_default_furniture,
    DROP CHECK chk_furniture_type,
    DROP CHECK chk_default_furniture_type_match,
    MODIFY COLUMN default_furniture_type VARCHAR(20) NULL,
    MODIFY COLUMN furniture_type VARCHAR(20) NULL;

UPDATE items
SET default_furniture_type = NULL, furniture_type = NULL
WHERE furniture_type = 'FRIDGE' OR default_furniture_type = 'FRIDGE';

UPDATE items
SET furniture_type = CASE
    WHEN asset_key IN ('dining_table_original', 'dining_table_black', 'dining_table_pink', 'dining_table_sunset') THEN 'DINING_TABLE'
    WHEN asset_key IN ('coffee_table_original', 'coffee_table_black', 'coffee_table_pink', 'coffee_table_sunset') THEN 'COFFEE_TABLE'
END
WHERE item_category = 'FURNITURE' AND asset_key IN (
    'dining_table_original', 'dining_table_black', 'dining_table_pink', 'dining_table_sunset',
    'coffee_table_original', 'coffee_table_black', 'coffee_table_pink', 'coffee_table_sunset'
);

UPDATE items
SET default_furniture_type = furniture_type, price = 0, is_active = FALSE
WHERE asset_key IN ('dining_table_original', 'coffee_table_original') AND item_category = 'FURNITURE';

ALTER TABLE items
    ADD CONSTRAINT chk_default_furniture CHECK (
        default_furniture_type IS NULL OR (
            default_furniture_type IN ('SOFA', 'TV', 'DINING_TABLE', 'COFFEE_TABLE')
            AND item_category = 'FURNITURE' AND slot_type = 'FLOOR'
            AND price = 0 AND is_active = FALSE
        )
    ),
    ADD CONSTRAINT chk_furniture_type CHECK (
        furniture_type IS NULL OR (
            furniture_type IN ('SOFA', 'TV', 'DINING_TABLE', 'COFFEE_TABLE')
            AND item_category = 'FURNITURE' AND slot_type = 'FLOOR'
        )
    ),
    ADD CONSTRAINT chk_default_furniture_type_match CHECK (
        default_furniture_type IS NULL OR (
            furniture_type IS NOT NULL AND furniture_type = default_furniture_type
        )
    );

-- Tables were ordinary furniture on V23. Keep the oldest installed instance
-- of each type; move only additional installed variants into storage.
UPDATE user_furnitures uf
JOIN items i ON i.id = uf.item_id
JOIN users u ON u.id = uf.user_id
JOIN (
    SELECT placed.user_id, item.furniture_type, MIN(placed.id) AS keeper_id
    FROM user_furnitures placed JOIN items item ON item.id = placed.item_id
    WHERE placed.placement_status IS NOT NULL
      AND item.furniture_type IN ('DINING_TABLE', 'COFFEE_TABLE')
    GROUP BY placed.user_id, item.furniture_type
) keepers ON keepers.user_id = uf.user_id AND keepers.furniture_type = i.furniture_type
SET uf.placement_status = NULL, uf.placement_direction = NULL,
    uf.position_x = NULL, uf.position_y = NULL, uf.layer = 0, uf.sticker_attached = FALSE
WHERE u.deleted_at IS NULL AND uf.placement_status IS NOT NULL AND uf.id <> keepers.keeper_id;

-- Acquire missing starter tables without duplicating previously purchased items.
INSERT INTO user_furnitures (user_id, item_id)
SELECT u.id, i.id
FROM users u CROSS JOIN items i
WHERE u.deleted_at IS NULL AND i.default_furniture_type IN ('DINING_TABLE', 'COFFEE_TABLE')
  AND NOT EXISTS (SELECT 1 FROM user_furnitures owned WHERE owned.user_id = u.id AND owned.item_id = i.id);

-- Leave an installed variant's position/direction/layer untouched. Only install
-- a starter if no item of its type is already installed. Anchors match DEFAULT_CELLS.
UPDATE user_furnitures uf
JOIN items i ON i.id = uf.item_id
JOIN users u ON u.id = uf.user_id
LEFT JOIN (
    SELECT placed.user_id, item.furniture_type, MIN(placed.id) AS installed_id
    FROM user_furnitures placed JOIN items item ON item.id = placed.item_id
    WHERE placed.placement_status IS NOT NULL
      AND item.furniture_type IN ('DINING_TABLE', 'COFFEE_TABLE')
    GROUP BY placed.user_id, item.furniture_type
) installed ON installed.user_id = uf.user_id AND installed.furniture_type = i.furniture_type
SET uf.placement_status = 'FLOOR', uf.placement_direction = 'FRONT_RIGHT',
    uf.position_x = CASE i.default_furniture_type WHEN 'DINING_TABLE' THEN 64.604 ELSE 127.417 END,
    uf.position_y = CASE i.default_furniture_type WHEN 'DINING_TABLE' THEN 362.438 ELSE 429.875 END,
    uf.layer = 0
WHERE u.deleted_at IS NULL AND i.default_furniture_type IN ('DINING_TABLE', 'COFFEE_TABLE')
  AND installed.installed_id IS NULL;
