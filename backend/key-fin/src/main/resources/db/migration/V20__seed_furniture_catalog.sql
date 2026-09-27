-- Mobile-bundled furniture. Two views share one item; colors are separate items.
-- Default furniture originals, tabletop accessories and hanging plants are excluded.
-- Validate the entire target set before a single atomic INSERT (InnoDB).
-- Explicit key collation handles JSON_TABLE/MySQL connection collation differences;
-- binary field validation below rejects case/spacing variants instead of reusing them.
DROP PROCEDURE IF EXISTS seed_furniture_catalog_v20;

DELIMITER $$
CREATE PROCEDURE seed_furniture_catalog_v20()
BEGIN
    DECLARE catalog JSON DEFAULT '[
        {"assetKey":"desk_original","name":"원목 책상 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"coffee_table_original","name":"커피 테이블 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_table_original","name":"식탁 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_chair_original","name":"식탁 의자 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"bed_original","name":"침대 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"nightstand_original","name":"협탁 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"bookcase_original","name":"책장 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"wardrobe_original","name":"옷장 (오리지널)","slotType":"FLOOR","price":500},
        {"assetKey":"sofa_black","name":"2인 소파 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"desk_black","name":"원목 책상 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"coffee_table_black","name":"커피 테이블 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"refrigerator_black","name":"냉장고 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_table_black","name":"식탁 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_chair_black","name":"식탁 의자 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"bed_black","name":"침대 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"nightstand_black","name":"협탁 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"bookcase_black","name":"책장 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"wardrobe_black","name":"옷장 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"sofa_pink","name":"2인 소파 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"desk_pink","name":"원목 책상 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"coffee_table_pink","name":"커피 테이블 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"refrigerator_pink","name":"냉장고 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_table_pink","name":"식탁 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_chair_pink","name":"식탁 의자 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"bed_pink","name":"침대 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"nightstand_pink","name":"협탁 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"bookcase_pink","name":"책장 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"wardrobe_pink","name":"옷장 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"sofa_sunset","name":"2인 소파 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"desk_sunset","name":"원목 책상 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"coffee_table_sunset","name":"커피 테이블 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"refrigerator_sunset","name":"냉장고 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_table_sunset","name":"식탁 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"dining_chair_sunset","name":"식탁 의자 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"bed_sunset","name":"침대 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"nightstand_sunset","name":"협탁 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"bookcase_sunset","name":"책장 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"wardrobe_sunset","name":"옷장 (선셋 팝)","slotType":"FLOOR","price":500},
        {"assetKey":"plant_monstera_terracotta","name":"테라코타 몬스테라","slotType":"FLOOR","price":200},
        {"assetKey":"plant_sansevieria_ivory","name":"세로줄 도자기 산세베리아","slotType":"FLOOR","price":200},
        {"assetKey":"plant_rubber_brass","name":"황동 스탠드 고무나무","slotType":"FLOOR","price":200},
        {"assetKey":"plant_palm_blue_wave","name":"블루 웨이브 야자","slotType":"FLOOR","price":200},
        {"assetKey":"decor_abstract_frame","name":"추상 벽액자","slotType":"WALL","price":300},
        {"assetKey":"decor_botanical_frame","name":"식물 벽액자","slotType":"WALL","price":300},
        {"assetKey":"decor_wave_poster","name":"물결 패브릭 포스터","slotType":"WALL","price":300},
        {"assetKey":"decor_arch_poster","name":"아치 패브릭 포스터","slotType":"WALL","price":300},
        {"assetKey":"decor_round_wall_clock","name":"원형 벽시계","slotType":"WALL","price":300},
        {"assetKey":"decor_arc_floor_lamp","name":"아치 플로어램프","slotType":"FLOOR","price":200},
        {"assetKey":"decor_oval_rug","name":"타원 러그","slotType":"FLOOR","price":200},
        {"assetKey":"decor_checker_rug","name":"체커 러그","slotType":"FLOOR","price":200},
        {"assetKey":"decor_round_mirror","name":"둥근 벽거울","slotType":"WALL","price":300},
        {"assetKey":"decor_wall_shelf","name":"벽선반","slotType":"WALL","price":300},
        {"assetKey":"window_sky_clouds","name":"하늘과 구름 창문","slotType":"WALL","price":300},
        {"assetKey":"tv_set_black","name":"TV·TV장 세트 (블랙)","slotType":"FLOOR","price":500},
        {"assetKey":"tv_set_pink","name":"TV·TV장 세트 (핑크)","slotType":"FLOOR","price":500},
        {"assetKey":"tv_set_sunset","name":"TV·TV장 세트 (선셋 팝)","slotType":"FLOOR","price":500}
    ]';

    IF EXISTS (
        SELECT seed.asset_key FROM items i
        JOIN JSON_TABLE(catalog, '$[*]' COLUMNS (asset_key VARCHAR(100) PATH '$.assetKey')) seed
            ON i.asset_key = seed.asset_key COLLATE utf8mb4_unicode_ci
        GROUP BY seed.asset_key HAVING COUNT(*) > 1
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V20 furniture asset keys must identify a single item';
    END IF;

    IF EXISTS (
        SELECT 1 FROM items i
        JOIN JSON_TABLE(catalog, '$[*]' COLUMNS (
            asset_key VARCHAR(100) PATH '$.assetKey', name VARCHAR(50) PATH '$.name',
            slot_type VARCHAR(20) PATH '$.slotType', price INT PATH '$.price'
        )) seed ON i.asset_key = seed.asset_key COLLATE utf8mb4_unicode_ci
        WHERE BINARY i.asset_key <> BINARY seed.asset_key
            OR BINARY i.item_category <> BINARY 'FURNITURE'
            OR BINARY i.slot_type <> BINARY seed.slot_type OR BINARY i.name <> BINARY seed.name
            OR i.price <> seed.price OR i.theme_code IS NOT NULL OR i.is_active <> FALSE
            OR i.default_furniture_type IS NOT NULL
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V20 furniture catalog conflicts with existing items; review before retry';
    END IF;

    INSERT INTO items (item_category, slot_type, name, price, asset_key, theme_code, is_active, default_furniture_type)
    SELECT 'FURNITURE', seed.slot_type, seed.name, seed.price, seed.asset_key, NULL, FALSE, NULL
    FROM JSON_TABLE(catalog, '$[*]' COLUMNS (
        asset_key VARCHAR(100) PATH '$.assetKey', name VARCHAR(50) PATH '$.name',
        slot_type VARCHAR(20) PATH '$.slotType', price INT PATH '$.price'
    )) seed
    WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.asset_key = seed.asset_key COLLATE utf8mb4_unicode_ci);
END$$
DELIMITER ;

CALL seed_furniture_catalog_v20();
DROP PROCEDURE seed_furniture_catalog_v20;
