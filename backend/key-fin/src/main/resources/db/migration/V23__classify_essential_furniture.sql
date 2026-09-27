-- Keep default_furniture_type as the non-sale starter item identity.
-- furniture_type groups starter items and the V20 color variants by room role.
ALTER TABLE items ADD COLUMN furniture_type VARCHAR(10) NULL;

UPDATE items
SET furniture_type = CASE
    WHEN asset_key IN ('fridge_default', 'refrigerator_black', 'refrigerator_pink', 'refrigerator_sunset') THEN 'FRIDGE'
    WHEN asset_key IN ('sofa_default', 'sofa_black', 'sofa_pink', 'sofa_sunset') THEN 'SOFA'
    WHEN asset_key IN ('tv_default', 'tv_set_black', 'tv_set_pink', 'tv_set_sunset') THEN 'TV'
    ELSE NULL
END
WHERE item_category = 'FURNITURE';

ALTER TABLE items
    ADD CONSTRAINT chk_furniture_type CHECK (
        furniture_type IS NULL OR (
            furniture_type IN ('FRIDGE', 'SOFA', 'TV')
            AND item_category = 'FURNITURE' AND slot_type = 'FLOOR'
        )
    ),
    ADD CONSTRAINT chk_default_furniture_type_match CHECK (
        default_furniture_type IS NULL OR (
            furniture_type IS NOT NULL AND furniture_type = default_furniture_type
        )
    );
