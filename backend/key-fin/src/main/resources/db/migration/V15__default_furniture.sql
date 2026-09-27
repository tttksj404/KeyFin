ALTER TABLE items
    ADD COLUMN default_furniture_type VARCHAR(10) NULL,
    ADD CONSTRAINT uq_default_furniture_type UNIQUE (default_furniture_type);

-- Reuse the oldest matching catalogue item; other variants remain ordinary furniture.
UPDATE items i
JOIN (
    SELECT asset_key, MIN(id) AS id FROM items
    WHERE item_category = 'FURNITURE' AND slot_type = 'FLOOR'
      AND asset_key IN ('fridge_default', 'sofa_default', 'tv_default')
    GROUP BY asset_key
) existing ON existing.id = i.id
SET i.default_furniture_type = CASE i.asset_key
        WHEN 'fridge_default' THEN 'FRIDGE' WHEN 'sofa_default' THEN 'SOFA' ELSE 'TV' END,
    i.price = 0, i.is_active = FALSE;

INSERT INTO items (item_category, slot_type, name, price, asset_key, is_active, default_furniture_type)
SELECT 'FURNITURE', 'FLOOR', seed.name, 0, seed.asset_key, FALSE, seed.kind
FROM (
    SELECT 'FRIDGE' AS kind, '냉장고' AS name, 'fridge_default' AS asset_key
    UNION ALL SELECT 'SOFA', '소파', 'sofa_default'
    UNION ALL SELECT 'TV', 'TV', 'tv_default'
) seed
WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.default_furniture_type = seed.kind);

ALTER TABLE items
    ADD CONSTRAINT chk_default_furniture CHECK (
        default_furniture_type IS NULL OR (
            default_furniture_type IN ('FRIDGE', 'SOFA', 'TV')
            AND item_category = 'FURNITURE' AND slot_type = 'FLOOR'
            AND price = 0 AND is_active = FALSE
        )
    );

-- Coordinates mirror the current room's fridge, sofa and desk anchors (TV uses the desk position).
INSERT INTO user_furnitures
    (user_id, item_id, placement_status, placement_direction, position_x, position_y, layer)
SELECT u.id, i.id, 'FLOOR', 'FRONT_RIGHT',
       CASE i.default_furniture_type WHEN 'FRIDGE' THEN 280.438 WHEN 'SOFA' THEN 164.875 ELSE 172.719 END,
       CASE i.default_furniture_type WHEN 'FRIDGE' THEN 217.813 WHEN 'SOFA' THEN 226.000 ELSE 176.094 END, 0
FROM users u CROSS JOIN items i
WHERE u.deleted_at IS NULL AND i.default_furniture_type IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM user_furnitures uf WHERE uf.user_id = u.id AND uf.item_id = i.id);

UPDATE user_furnitures uf
JOIN items i ON i.id = uf.item_id
JOIN users u ON u.id = uf.user_id
SET uf.placement_status = 'FLOOR', uf.placement_direction = 'FRONT_RIGHT',
    uf.position_x = CASE i.default_furniture_type WHEN 'FRIDGE' THEN 280.438 WHEN 'SOFA' THEN 164.875 ELSE 172.719 END,
    uf.position_y = CASE i.default_furniture_type WHEN 'FRIDGE' THEN 217.813 WHEN 'SOFA' THEN 226.000 ELSE 176.094 END,
    uf.layer = 0
WHERE u.deleted_at IS NULL AND i.default_furniture_type IS NOT NULL AND uf.placement_status IS NULL;
