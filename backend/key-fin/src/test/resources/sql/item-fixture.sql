INSERT INTO users (id, email, password, name, deleted_at) VALUES
 (971, 'item-owner@keyfin.io', 'x', '아이템 소유자', NULL),
 (972, 'item-other@keyfin.io', 'x', '다른 사용자', NULL),
 (973, 'item-empty@keyfin.io', 'x', '빈 옷장', NULL),
 (974, 'item-deleted@keyfin.io', 'x', '탈퇴 사용자', '2026-09-01 00:00:00');

INSERT INTO items (id, item_category, slot_type, name, price, asset_key, is_active) VALUES
 (7101, 'AVATAR', 'HEAD', '모자', 10, 'hat_blue', TRUE),
 (7102, 'AVATAR', 'FACE', '안경', 10, 'glasses_round', TRUE),
 (7103, 'AVATAR', 'UPPER_BODY', '셔츠 A', 10, 'shirt_a', TRUE),
 (7104, 'AVATAR', 'UPPER_BODY', '셔츠 B', 10, 'shirt_b', FALSE),
 (7105, 'AVATAR', 'LOWER_BODY', '바지', 10, 'pants_blue', TRUE),
 (7106, 'AVATAR', 'SOCKS', '양말', 10, 'socks_white', TRUE),
 (7107, 'AVATAR', 'FOOTWEAR', '신발', 10, 'shoes_black', TRUE),
 (7108, 'FURNITURE', 'FLOOR', '소파', 10, 'sofa_blue', TRUE);

INSERT INTO user_items (id, user_id, item_id, equipped_slot) VALUES
 (7201, 971, 7103, 'UPPER_BODY'),
 (7202, 971, 7104, NULL),
 (7203, 971, 7101, 'HEAD'),
 (7204, 971, 7102, NULL),
 (7205, 971, 7105, NULL),
 (7206, 971, 7106, NULL),
 (7207, 971, 7107, NULL),
 (7208, 972, 7101, 'HEAD');

INSERT INTO user_furnitures (id, user_id, item_id) VALUES (7301, 971, 7108);
