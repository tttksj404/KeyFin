/**
 * 가구 스프라이트. scripts/assets/build-furniture-sprites.ps1 이 원본(방향별 2장)에서 여백을 잘라 만든 그림이다.
 * - left: 왼쪽 벽을 등진 그림(FRONT_RIGHT) · right: 오른쪽 벽을 등진 그림(FRONT_LEFT) · shop: 상점 타일용 축소본(left 기준)
 * Metro 는 require 경로가 문자열 상수여야 해서 한 줄씩 적는다. 키는 서버 items.asset_key 다.
 */
export type FurnitureSpriteSet = { left: number; right: number; shop: number };

export const FURNITURE_SPRITES = {
  bed_black: {
    left: require("@/assets/sprites/furniture/bed_black/left.png"),
    right: require("@/assets/sprites/furniture/bed_black/right.png"),
    shop: require("@/assets/sprites/furniture/bed_black/shop.png"),
  },
  bed_original: {
    left: require("@/assets/sprites/furniture/bed_original/left.png"),
    right: require("@/assets/sprites/furniture/bed_original/right.png"),
    shop: require("@/assets/sprites/furniture/bed_original/shop.png"),
  },
  bed_pink: {
    left: require("@/assets/sprites/furniture/bed_pink/left.png"),
    right: require("@/assets/sprites/furniture/bed_pink/right.png"),
    shop: require("@/assets/sprites/furniture/bed_pink/shop.png"),
  },
  bed_sunset: {
    left: require("@/assets/sprites/furniture/bed_sunset/left.png"),
    right: require("@/assets/sprites/furniture/bed_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/bed_sunset/shop.png"),
  },
  bookcase_black: {
    left: require("@/assets/sprites/furniture/bookcase_black/left.png"),
    right: require("@/assets/sprites/furniture/bookcase_black/right.png"),
    shop: require("@/assets/sprites/furniture/bookcase_black/shop.png"),
  },
  bookcase_original: {
    left: require("@/assets/sprites/furniture/bookcase_original/left.png"),
    right: require("@/assets/sprites/furniture/bookcase_original/right.png"),
    shop: require("@/assets/sprites/furniture/bookcase_original/shop.png"),
  },
  bookcase_pink: {
    left: require("@/assets/sprites/furniture/bookcase_pink/left.png"),
    right: require("@/assets/sprites/furniture/bookcase_pink/right.png"),
    shop: require("@/assets/sprites/furniture/bookcase_pink/shop.png"),
  },
  bookcase_sunset: {
    left: require("@/assets/sprites/furniture/bookcase_sunset/left.png"),
    right: require("@/assets/sprites/furniture/bookcase_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/bookcase_sunset/shop.png"),
  },
  coffee_table_black: {
    left: require("@/assets/sprites/furniture/coffee_table_black/left.png"),
    right: require("@/assets/sprites/furniture/coffee_table_black/right.png"),
    shop: require("@/assets/sprites/furniture/coffee_table_black/shop.png"),
  },
  coffee_table_original: {
    left: require("@/assets/sprites/furniture/coffee_table_original/left.png"),
    right: require("@/assets/sprites/furniture/coffee_table_original/right.png"),
    shop: require("@/assets/sprites/furniture/coffee_table_original/shop.png"),
  },
  coffee_table_pink: {
    left: require("@/assets/sprites/furniture/coffee_table_pink/left.png"),
    right: require("@/assets/sprites/furniture/coffee_table_pink/right.png"),
    shop: require("@/assets/sprites/furniture/coffee_table_pink/shop.png"),
  },
  coffee_table_sunset: {
    left: require("@/assets/sprites/furniture/coffee_table_sunset/left.png"),
    right: require("@/assets/sprites/furniture/coffee_table_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/coffee_table_sunset/shop.png"),
  },
  decor_abstract_frame: {
    left: require("@/assets/sprites/furniture/decor_abstract_frame/left.png"),
    right: require("@/assets/sprites/furniture/decor_abstract_frame/right.png"),
    shop: require("@/assets/sprites/furniture/decor_abstract_frame/shop.png"),
  },
  decor_arc_floor_lamp: {
    left: require("@/assets/sprites/furniture/decor_arc_floor_lamp/left.png"),
    right: require("@/assets/sprites/furniture/decor_arc_floor_lamp/right.png"),
    shop: require("@/assets/sprites/furniture/decor_arc_floor_lamp/shop.png"),
  },
  decor_arch_poster: {
    left: require("@/assets/sprites/furniture/decor_arch_poster/left.png"),
    right: require("@/assets/sprites/furniture/decor_arch_poster/right.png"),
    shop: require("@/assets/sprites/furniture/decor_arch_poster/shop.png"),
  },
  decor_botanical_frame: {
    left: require("@/assets/sprites/furniture/decor_botanical_frame/left.png"),
    right: require("@/assets/sprites/furniture/decor_botanical_frame/right.png"),
    shop: require("@/assets/sprites/furniture/decor_botanical_frame/shop.png"),
  },
  decor_checker_rug: {
    left: require("@/assets/sprites/furniture/decor_checker_rug/left.png"),
    right: require("@/assets/sprites/furniture/decor_checker_rug/right.png"),
    shop: require("@/assets/sprites/furniture/decor_checker_rug/shop.png"),
  },
  decor_oval_rug: {
    left: require("@/assets/sprites/furniture/decor_oval_rug/left.png"),
    right: require("@/assets/sprites/furniture/decor_oval_rug/right.png"),
    shop: require("@/assets/sprites/furniture/decor_oval_rug/shop.png"),
  },
  decor_round_mirror: {
    left: require("@/assets/sprites/furniture/decor_round_mirror/left.png"),
    right: require("@/assets/sprites/furniture/decor_round_mirror/right.png"),
    shop: require("@/assets/sprites/furniture/decor_round_mirror/shop.png"),
  },
  decor_round_wall_clock: {
    left: require("@/assets/sprites/furniture/decor_round_wall_clock/left.png"),
    right: require("@/assets/sprites/furniture/decor_round_wall_clock/right.png"),
    shop: require("@/assets/sprites/furniture/decor_round_wall_clock/shop.png"),
  },
  decor_wall_shelf: {
    left: require("@/assets/sprites/furniture/decor_wall_shelf/left.png"),
    right: require("@/assets/sprites/furniture/decor_wall_shelf/right.png"),
    shop: require("@/assets/sprites/furniture/decor_wall_shelf/shop.png"),
  },
  decor_wave_poster: {
    left: require("@/assets/sprites/furniture/decor_wave_poster/left.png"),
    right: require("@/assets/sprites/furniture/decor_wave_poster/right.png"),
    shop: require("@/assets/sprites/furniture/decor_wave_poster/shop.png"),
  },
  desk_black: {
    left: require("@/assets/sprites/furniture/desk_black/left.png"),
    right: require("@/assets/sprites/furniture/desk_black/right.png"),
    shop: require("@/assets/sprites/furniture/desk_black/shop.png"),
  },
  desk_original: {
    left: require("@/assets/sprites/furniture/desk_original/left.png"),
    right: require("@/assets/sprites/furniture/desk_original/right.png"),
    shop: require("@/assets/sprites/furniture/desk_original/shop.png"),
  },
  desk_pink: {
    left: require("@/assets/sprites/furniture/desk_pink/left.png"),
    right: require("@/assets/sprites/furniture/desk_pink/right.png"),
    shop: require("@/assets/sprites/furniture/desk_pink/shop.png"),
  },
  desk_sunset: {
    left: require("@/assets/sprites/furniture/desk_sunset/left.png"),
    right: require("@/assets/sprites/furniture/desk_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/desk_sunset/shop.png"),
  },
  dining_chair_black: {
    left: require("@/assets/sprites/furniture/dining_chair_black/left.png"),
    right: require("@/assets/sprites/furniture/dining_chair_black/right.png"),
    shop: require("@/assets/sprites/furniture/dining_chair_black/shop.png"),
  },
  dining_chair_original: {
    left: require("@/assets/sprites/furniture/dining_chair_original/left.png"),
    right: require("@/assets/sprites/furniture/dining_chair_original/right.png"),
    shop: require("@/assets/sprites/furniture/dining_chair_original/shop.png"),
  },
  dining_chair_pink: {
    left: require("@/assets/sprites/furniture/dining_chair_pink/left.png"),
    right: require("@/assets/sprites/furniture/dining_chair_pink/right.png"),
    shop: require("@/assets/sprites/furniture/dining_chair_pink/shop.png"),
  },
  dining_chair_sunset: {
    left: require("@/assets/sprites/furniture/dining_chair_sunset/left.png"),
    right: require("@/assets/sprites/furniture/dining_chair_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/dining_chair_sunset/shop.png"),
  },
  dining_table_black: {
    left: require("@/assets/sprites/furniture/dining_table_black/left.png"),
    right: require("@/assets/sprites/furniture/dining_table_black/right.png"),
    shop: require("@/assets/sprites/furniture/dining_table_black/shop.png"),
  },
  dining_table_original: {
    left: require("@/assets/sprites/furniture/dining_table_original/left.png"),
    right: require("@/assets/sprites/furniture/dining_table_original/right.png"),
    shop: require("@/assets/sprites/furniture/dining_table_original/shop.png"),
  },
  dining_table_pink: {
    left: require("@/assets/sprites/furniture/dining_table_pink/left.png"),
    right: require("@/assets/sprites/furniture/dining_table_pink/right.png"),
    shop: require("@/assets/sprites/furniture/dining_table_pink/shop.png"),
  },
  dining_table_sunset: {
    left: require("@/assets/sprites/furniture/dining_table_sunset/left.png"),
    right: require("@/assets/sprites/furniture/dining_table_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/dining_table_sunset/shop.png"),
  },
  nightstand_black: {
    left: require("@/assets/sprites/furniture/nightstand_black/left.png"),
    right: require("@/assets/sprites/furniture/nightstand_black/right.png"),
    shop: require("@/assets/sprites/furniture/nightstand_black/shop.png"),
  },
  nightstand_original: {
    left: require("@/assets/sprites/furniture/nightstand_original/left.png"),
    right: require("@/assets/sprites/furniture/nightstand_original/right.png"),
    shop: require("@/assets/sprites/furniture/nightstand_original/shop.png"),
  },
  nightstand_pink: {
    left: require("@/assets/sprites/furniture/nightstand_pink/left.png"),
    right: require("@/assets/sprites/furniture/nightstand_pink/right.png"),
    shop: require("@/assets/sprites/furniture/nightstand_pink/shop.png"),
  },
  nightstand_sunset: {
    left: require("@/assets/sprites/furniture/nightstand_sunset/left.png"),
    right: require("@/assets/sprites/furniture/nightstand_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/nightstand_sunset/shop.png"),
  },
  plant_monstera_terracotta: {
    left: require("@/assets/sprites/furniture/plant_monstera_terracotta/left.png"),
    right: require("@/assets/sprites/furniture/plant_monstera_terracotta/right.png"),
    shop: require("@/assets/sprites/furniture/plant_monstera_terracotta/shop.png"),
  },
  plant_palm_blue_wave: {
    left: require("@/assets/sprites/furniture/plant_palm_blue_wave/left.png"),
    right: require("@/assets/sprites/furniture/plant_palm_blue_wave/right.png"),
    shop: require("@/assets/sprites/furniture/plant_palm_blue_wave/shop.png"),
  },
  plant_rubber_brass: {
    left: require("@/assets/sprites/furniture/plant_rubber_brass/left.png"),
    right: require("@/assets/sprites/furniture/plant_rubber_brass/right.png"),
    shop: require("@/assets/sprites/furniture/plant_rubber_brass/shop.png"),
  },
  plant_sansevieria_ivory: {
    left: require("@/assets/sprites/furniture/plant_sansevieria_ivory/left.png"),
    right: require("@/assets/sprites/furniture/plant_sansevieria_ivory/right.png"),
    shop: require("@/assets/sprites/furniture/plant_sansevieria_ivory/shop.png"),
  },
  refrigerator_black: {
    left: require("@/assets/sprites/furniture/refrigerator_black/left.png"),
    right: require("@/assets/sprites/furniture/refrigerator_black/right.png"),
    shop: require("@/assets/sprites/furniture/refrigerator_black/shop.png"),
  },
  refrigerator_original: {
    left: require("@/assets/sprites/furniture/refrigerator_original/left.png"),
    right: require("@/assets/sprites/furniture/refrigerator_original/right.png"),
    shop: require("@/assets/sprites/furniture/refrigerator_original/shop.png"),
  },
  refrigerator_pink: {
    left: require("@/assets/sprites/furniture/refrigerator_pink/left.png"),
    right: require("@/assets/sprites/furniture/refrigerator_pink/right.png"),
    shop: require("@/assets/sprites/furniture/refrigerator_pink/shop.png"),
  },
  refrigerator_sunset: {
    left: require("@/assets/sprites/furniture/refrigerator_sunset/left.png"),
    right: require("@/assets/sprites/furniture/refrigerator_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/refrigerator_sunset/shop.png"),
  },
  sofa_black: {
    left: require("@/assets/sprites/furniture/sofa_black/left.png"),
    right: require("@/assets/sprites/furniture/sofa_black/right.png"),
    shop: require("@/assets/sprites/furniture/sofa_black/shop.png"),
  },
  sofa_original: {
    left: require("@/assets/sprites/furniture/sofa_original/left.png"),
    right: require("@/assets/sprites/furniture/sofa_original/right.png"),
    shop: require("@/assets/sprites/furniture/sofa_original/shop.png"),
  },
  sofa_pink: {
    left: require("@/assets/sprites/furniture/sofa_pink/left.png"),
    right: require("@/assets/sprites/furniture/sofa_pink/right.png"),
    shop: require("@/assets/sprites/furniture/sofa_pink/shop.png"),
  },
  sofa_sunset: {
    left: require("@/assets/sprites/furniture/sofa_sunset/left.png"),
    right: require("@/assets/sprites/furniture/sofa_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/sofa_sunset/shop.png"),
  },
  tv_set_black: {
    left: require("@/assets/sprites/furniture/tv_set_black/left.png"),
    right: require("@/assets/sprites/furniture/tv_set_black/right.png"),
    shop: require("@/assets/sprites/furniture/tv_set_black/shop.png"),
  },
  tv_set_original: {
    left: require("@/assets/sprites/furniture/tv_set_original/left.png"),
    right: require("@/assets/sprites/furniture/tv_set_original/right.png"),
    shop: require("@/assets/sprites/furniture/tv_set_original/shop.png"),
  },
  tv_set_pink: {
    left: require("@/assets/sprites/furniture/tv_set_pink/left.png"),
    right: require("@/assets/sprites/furniture/tv_set_pink/right.png"),
    shop: require("@/assets/sprites/furniture/tv_set_pink/shop.png"),
  },
  tv_set_sunset: {
    left: require("@/assets/sprites/furniture/tv_set_sunset/left.png"),
    right: require("@/assets/sprites/furniture/tv_set_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/tv_set_sunset/shop.png"),
  },
  wardrobe_black: {
    left: require("@/assets/sprites/furniture/wardrobe_black/left.png"),
    right: require("@/assets/sprites/furniture/wardrobe_black/right.png"),
    shop: require("@/assets/sprites/furniture/wardrobe_black/shop.png"),
  },
  wardrobe_original: {
    left: require("@/assets/sprites/furniture/wardrobe_original/left.png"),
    right: require("@/assets/sprites/furniture/wardrobe_original/right.png"),
    shop: require("@/assets/sprites/furniture/wardrobe_original/shop.png"),
  },
  wardrobe_pink: {
    left: require("@/assets/sprites/furniture/wardrobe_pink/left.png"),
    right: require("@/assets/sprites/furniture/wardrobe_pink/right.png"),
    shop: require("@/assets/sprites/furniture/wardrobe_pink/shop.png"),
  },
  wardrobe_sunset: {
    left: require("@/assets/sprites/furniture/wardrobe_sunset/left.png"),
    right: require("@/assets/sprites/furniture/wardrobe_sunset/right.png"),
    shop: require("@/assets/sprites/furniture/wardrobe_sunset/shop.png"),
  },
  window_sky_clouds: {
    left: require("@/assets/sprites/furniture/window_sky_clouds/left.png"),
    right: require("@/assets/sprites/furniture/window_sky_clouds/right.png"),
    shop: require("@/assets/sprites/furniture/window_sky_clouds/shop.png"),
  },
} satisfies Record<string, FurnitureSpriteSet>;

export type FurnitureAssetKey = keyof typeof FURNITURE_SPRITES;
