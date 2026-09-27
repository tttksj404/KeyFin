INSERT INTO users (id, email, password, name, deleted_at) VALUES
 (88001, 'furniture-owner@keyfin.io', 'x', '가구 소유자', NULL),
 (88002, 'furniture-other@keyfin.io', 'x', '다른 사용자', NULL),
 (88003, 'furniture-empty@keyfin.io', 'x', '빈 방', NULL),
 (88004, 'furniture-deleted@keyfin.io', 'x', '탈퇴 사용자', '2026-09-01 00:00:00');

INSERT INTO items (id, item_category, slot_type, name, price, asset_key, is_active) VALUES
 (88101, 'FURNITURE', 'FLOOR', '소파', 10, 'sofa_blue', TRUE),
 (88102, 'FURNITURE', 'WALL', '액자', 10, 'frame_blue', TRUE),
 (88103, 'FURNITURE', 'FLOOR', '단종 책상', 10, 'desk_old', FALSE),
 (88104, 'AVATAR', 'HEAD', '모자', 10, 'hat_blue', TRUE);

INSERT INTO user_furnitures (id, user_id, item_id, placement_status, placement_direction, position_x, position_y, layer) VALUES
 (88203, 88001, 88103, NULL, NULL, NULL, NULL, 0),
 (88201, 88001, 88101, 'FLOOR', 'FRONT_LEFT', 165.123, 280.456, -2),
 (88202, 88001, 88102, 'LEFT_WALL', 'FRONT_RIGHT', 90.000, 80.000, 1),
 (88204, 88002, 88101, 'FLOOR', 'FRONT_RIGHT', 1.000, 2.000, 0);

INSERT INTO user_items (id, user_id, item_id, equipped_slot) VALUES (88301, 88001, 88104, 'HEAD');
