-- Mobile-bundled outfits: one item per set, with shop/standing/sitting images.
-- Prices are confirmed; sales remain disabled until the app supports these assets.
-- Validate before the single INSERT so conflicts cannot partially seed the catalog.
DROP PROCEDURE IF EXISTS seed_avatar_outfit_sets_v19;

DELIMITER $$
CREATE PROCEDURE seed_avatar_outfit_sets_v19()
BEGIN
    IF EXISTS (
        SELECT asset_key COLLATE utf8mb4_unicode_ci FROM items
        WHERE asset_key COLLATE utf8mb4_unicode_ci IN ('outfit_epic_mage', 'outfit_legendary_paladin', 'outfit_mythic_dragon')
        GROUP BY asset_key COLLATE utf8mb4_unicode_ci HAVING COUNT(*) > 1
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V19 outfit asset keys must identify a single item';
    END IF;

    IF EXISTS (
        SELECT 1 FROM items i
        JOIN (
            SELECT 'outfit_epic_mage' AS asset_key, '에픽 마법사 의상 세트' AS name, 500 AS price
            UNION ALL SELECT 'outfit_legendary_paladin', '레전더리 성기사 의상 세트', 1000
            UNION ALL SELECT 'outfit_mythic_dragon', '신화 용염 의상 세트', 2000
        ) seed ON i.asset_key = seed.asset_key COLLATE utf8mb4_unicode_ci
        WHERE BINARY i.asset_key <> BINARY seed.asset_key
            OR BINARY i.item_category <> BINARY 'AVATAR' OR BINARY i.slot_type <> BINARY 'UPPER_BODY'
            OR BINARY i.name <> BINARY seed.name OR i.price <> seed.price
            OR i.theme_code IS NOT NULL OR i.is_active <> FALSE
            OR i.default_furniture_type IS NOT NULL
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V19 outfit catalog conflicts with existing items; review before retry';
    END IF;

    INSERT INTO items (item_category, slot_type, name, price, asset_key, theme_code, is_active, default_furniture_type)
    SELECT 'AVATAR', 'UPPER_BODY', seed.name, seed.price, seed.asset_key, NULL, FALSE, NULL
    FROM (
        SELECT 'outfit_epic_mage' AS asset_key, '에픽 마법사 의상 세트' AS name, 500 AS price
        UNION ALL SELECT 'outfit_legendary_paladin', '레전더리 성기사 의상 세트', 1000
        UNION ALL SELECT 'outfit_mythic_dragon', '신화 용염 의상 세트', 2000
    ) seed
    WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.asset_key = seed.asset_key COLLATE utf8mb4_unicode_ci);
END$$
DELIMITER ;

CALL seed_avatar_outfit_sets_v19();
DROP PROCEDURE seed_avatar_outfit_sets_v19;
