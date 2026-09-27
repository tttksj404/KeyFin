/**
 * 백엔드 마이그레이션 V24까지 적용한 판매 상품의 계약 사본.
 * - 의상: V19__seed_avatar_outfit_sets.sql — 3종, 모두 AVATAR · UPPER_BODY
 * - 가구: V20의 56종 중 V24에서 기본 지급으로 전환한 식탁·커피테이블 오리지널을 제외한 54종
 * 목(api/mocks/shop.ts)과 앱 카탈로그(features/room/catalog.ts · outfits.ts)가 이 값과 같은지 shop 모델 테스트가 확인한다.
 * 백엔드 판매 구성이 바뀌면 SQL 적용 결과를 반영한다. 판매 활성화는 V21, 기본 지급 전환은 V24가 담당한다.
 */
export type SeededItem = { assetKey: string; name: string; slotType: string; price: number };

export const SEEDED_OUTFITS: readonly SeededItem[] = [
  { assetKey: "outfit_epic_mage", name: "에픽 마법사 의상 세트", slotType: "UPPER_BODY", price: 500 },
  { assetKey: "outfit_legendary_paladin", name: "레전더리 성기사 의상 세트", slotType: "UPPER_BODY", price: 1000 },
  { assetKey: "outfit_mythic_dragon", name: "신화 용염 의상 세트", slotType: "UPPER_BODY", price: 2000 },
];

export const SEEDED_FURNITURE: readonly SeededItem[] = [
  { assetKey: "desk_original", name: "원목 책상 (오리지널)", slotType: "FLOOR", price: 500 },
  { assetKey: "dining_chair_original", name: "식탁 의자 (오리지널)", slotType: "FLOOR", price: 500 },
  { assetKey: "bed_original", name: "침대 (오리지널)", slotType: "FLOOR", price: 500 },
  { assetKey: "nightstand_original", name: "협탁 (오리지널)", slotType: "FLOOR", price: 500 },
  { assetKey: "bookcase_original", name: "책장 (오리지널)", slotType: "FLOOR", price: 500 },
  { assetKey: "wardrobe_original", name: "옷장 (오리지널)", slotType: "FLOOR", price: 500 },
  { assetKey: "sofa_black", name: "2인 소파 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "desk_black", name: "원목 책상 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "coffee_table_black", name: "커피 테이블 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "refrigerator_black", name: "냉장고 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "dining_table_black", name: "식탁 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "dining_chair_black", name: "식탁 의자 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "bed_black", name: "침대 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "nightstand_black", name: "협탁 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "bookcase_black", name: "책장 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "wardrobe_black", name: "옷장 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "sofa_pink", name: "2인 소파 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "desk_pink", name: "원목 책상 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "coffee_table_pink", name: "커피 테이블 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "refrigerator_pink", name: "냉장고 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "dining_table_pink", name: "식탁 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "dining_chair_pink", name: "식탁 의자 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "bed_pink", name: "침대 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "nightstand_pink", name: "협탁 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "bookcase_pink", name: "책장 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "wardrobe_pink", name: "옷장 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "sofa_sunset", name: "2인 소파 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "desk_sunset", name: "원목 책상 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "coffee_table_sunset", name: "커피 테이블 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "refrigerator_sunset", name: "냉장고 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "dining_table_sunset", name: "식탁 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "dining_chair_sunset", name: "식탁 의자 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "bed_sunset", name: "침대 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "nightstand_sunset", name: "협탁 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "bookcase_sunset", name: "책장 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "wardrobe_sunset", name: "옷장 (선셋 팝)", slotType: "FLOOR", price: 500 },
  { assetKey: "plant_monstera_terracotta", name: "테라코타 몬스테라", slotType: "FLOOR", price: 200 },
  { assetKey: "plant_sansevieria_ivory", name: "세로줄 도자기 산세베리아", slotType: "FLOOR", price: 200 },
  { assetKey: "plant_rubber_brass", name: "황동 스탠드 고무나무", slotType: "FLOOR", price: 200 },
  { assetKey: "plant_palm_blue_wave", name: "블루 웨이브 야자", slotType: "FLOOR", price: 200 },
  { assetKey: "decor_abstract_frame", name: "추상 벽액자", slotType: "WALL", price: 300 },
  { assetKey: "decor_botanical_frame", name: "식물 벽액자", slotType: "WALL", price: 300 },
  { assetKey: "decor_wave_poster", name: "물결 패브릭 포스터", slotType: "WALL", price: 300 },
  { assetKey: "decor_arch_poster", name: "아치 패브릭 포스터", slotType: "WALL", price: 300 },
  { assetKey: "decor_round_wall_clock", name: "원형 벽시계", slotType: "WALL", price: 300 },
  { assetKey: "decor_arc_floor_lamp", name: "아치 플로어램프", slotType: "FLOOR", price: 200 },
  { assetKey: "decor_oval_rug", name: "타원 러그", slotType: "FLOOR", price: 200 },
  { assetKey: "decor_checker_rug", name: "체커 러그", slotType: "FLOOR", price: 200 },
  { assetKey: "decor_round_mirror", name: "둥근 벽거울", slotType: "WALL", price: 300 },
  { assetKey: "decor_wall_shelf", name: "벽선반", slotType: "WALL", price: 300 },
  { assetKey: "window_sky_clouds", name: "하늘과 구름 창문", slotType: "WALL", price: 300 },
  { assetKey: "tv_set_black", name: "TV·TV장 세트 (블랙)", slotType: "FLOOR", price: 500 },
  { assetKey: "tv_set_pink", name: "TV·TV장 세트 (핑크)", slotType: "FLOOR", price: 500 },
  { assetKey: "tv_set_sunset", name: "TV·TV장 세트 (선셋 팝)", slotType: "FLOOR", price: 500 },
];
