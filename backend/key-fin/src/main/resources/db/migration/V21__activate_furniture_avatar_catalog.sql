-- Enable sales for the 3 outfits and 56 furniture items seeded by V19 and V20.
-- Only is_active changes. Default furniture and unrelated items remain untouched.
-- Validate all target keys before the single UPDATE; already-active items are accepted.
DROP PROCEDURE IF EXISTS activate_furniture_avatar_catalog_v21;

DELIMITER $$
CREATE PROCEDURE activate_furniture_avatar_catalog_v21()
BEGIN
    DECLARE catalog JSON DEFAULT '[
        {"assetKey":"outfit_epic_mage","itemCategory":"AVATAR"},
        {"assetKey":"outfit_legendary_paladin","itemCategory":"AVATAR"},
        {"assetKey":"outfit_mythic_dragon","itemCategory":"AVATAR"},
        {"assetKey":"desk_original","itemCategory":"FURNITURE"},
        {"assetKey":"coffee_table_original","itemCategory":"FURNITURE"},
        {"assetKey":"dining_table_original","itemCategory":"FURNITURE"},
        {"assetKey":"dining_chair_original","itemCategory":"FURNITURE"},
        {"assetKey":"bed_original","itemCategory":"FURNITURE"},
        {"assetKey":"nightstand_original","itemCategory":"FURNITURE"},
        {"assetKey":"bookcase_original","itemCategory":"FURNITURE"},
        {"assetKey":"wardrobe_original","itemCategory":"FURNITURE"},
        {"assetKey":"sofa_black","itemCategory":"FURNITURE"},
        {"assetKey":"desk_black","itemCategory":"FURNITURE"},
        {"assetKey":"coffee_table_black","itemCategory":"FURNITURE"},
        {"assetKey":"refrigerator_black","itemCategory":"FURNITURE"},
        {"assetKey":"dining_table_black","itemCategory":"FURNITURE"},
        {"assetKey":"dining_chair_black","itemCategory":"FURNITURE"},
        {"assetKey":"bed_black","itemCategory":"FURNITURE"},
        {"assetKey":"nightstand_black","itemCategory":"FURNITURE"},
        {"assetKey":"bookcase_black","itemCategory":"FURNITURE"},
        {"assetKey":"wardrobe_black","itemCategory":"FURNITURE"},
        {"assetKey":"sofa_pink","itemCategory":"FURNITURE"},
        {"assetKey":"desk_pink","itemCategory":"FURNITURE"},
        {"assetKey":"coffee_table_pink","itemCategory":"FURNITURE"},
        {"assetKey":"refrigerator_pink","itemCategory":"FURNITURE"},
        {"assetKey":"dining_table_pink","itemCategory":"FURNITURE"},
        {"assetKey":"dining_chair_pink","itemCategory":"FURNITURE"},
        {"assetKey":"bed_pink","itemCategory":"FURNITURE"},
        {"assetKey":"nightstand_pink","itemCategory":"FURNITURE"},
        {"assetKey":"bookcase_pink","itemCategory":"FURNITURE"},
        {"assetKey":"wardrobe_pink","itemCategory":"FURNITURE"},
        {"assetKey":"sofa_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"desk_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"coffee_table_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"refrigerator_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"dining_table_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"dining_chair_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"bed_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"nightstand_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"bookcase_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"wardrobe_sunset","itemCategory":"FURNITURE"},
        {"assetKey":"plant_monstera_terracotta","itemCategory":"FURNITURE"},
        {"assetKey":"plant_sansevieria_ivory","itemCategory":"FURNITURE"},
        {"assetKey":"plant_rubber_brass","itemCategory":"FURNITURE"},
        {"assetKey":"plant_palm_blue_wave","itemCategory":"FURNITURE"},
        {"assetKey":"decor_abstract_frame","itemCategory":"FURNITURE"},
        {"assetKey":"decor_botanical_frame","itemCategory":"FURNITURE"},
        {"assetKey":"decor_wave_poster","itemCategory":"FURNITURE"},
        {"assetKey":"decor_arch_poster","itemCategory":"FURNITURE"},
        {"assetKey":"decor_round_wall_clock","itemCategory":"FURNITURE"},
        {"assetKey":"decor_arc_floor_lamp","itemCategory":"FURNITURE"},
        {"assetKey":"decor_oval_rug","itemCategory":"FURNITURE"},
        {"assetKey":"decor_checker_rug","itemCategory":"FURNITURE"},
        {"assetKey":"decor_round_mirror","itemCategory":"FURNITURE"},
        {"assetKey":"decor_wall_shelf","itemCategory":"FURNITURE"},
        {"assetKey":"window_sky_clouds","itemCategory":"FURNITURE"},
        {"assetKey":"tv_set_black","itemCategory":"FURNITURE"},
        {"assetKey":"tv_set_pink","itemCategory":"FURNITURE"},
        {"assetKey":"tv_set_sunset","itemCategory":"FURNITURE"}
    ]';

    IF EXISTS (
        SELECT target.asset_key
        FROM JSON_TABLE(catalog, '$[*]' COLUMNS (
            asset_key VARCHAR(100) PATH '$.assetKey',
            item_category VARCHAR(20) PATH '$.itemCategory'
        )) target
        LEFT JOIN items i ON i.asset_key = target.asset_key COLLATE utf8mb4_unicode_ci
        GROUP BY target.asset_key, target.item_category
        HAVING COUNT(i.id) <> 1
            OR SUM(BINARY i.asset_key = BINARY target.asset_key
                AND BINARY i.item_category = BINARY target.item_category
                AND i.default_furniture_type IS NULL) <> 1
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'V21 catalog requires one matching non-default item per asset key';
    END IF;

    UPDATE items i
    JOIN JSON_TABLE(catalog, '$[*]' COLUMNS (
        asset_key VARCHAR(100) PATH '$.assetKey'
    )) target ON i.asset_key = target.asset_key COLLATE utf8mb4_unicode_ci
    SET i.is_active = TRUE
    WHERE i.is_active = FALSE;
END$$
DELIMITER ;

CALL activate_furniture_avatar_catalog_v21();
DROP PROCEDURE activate_furniture_avatar_catalog_v21;
