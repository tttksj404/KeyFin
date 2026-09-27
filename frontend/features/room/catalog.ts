import { HALF_PER_CELL, type GridFootprint } from "@/features/room/grid";
import { FURNITURE_SPRITES, type FurnitureAssetKey, type FurnitureSpriteSet } from "@/features/room/furniture-sprites";
import { FURNITURE_GEOMETRY } from "@/features/room/furniture-geometry.generated";
import type { AnchorRatio, PlacementDirection, SceneSize, Surface } from "@/features/room/model";
import { spriteRenderView, type FurnitureSpriteGeometry, type SpriteGeometry } from "@/features/room/sprite-geometry";

const SPRITE_GEOMETRY: Partial<Record<FurnitureAssetKey, FurnitureSpriteGeometry>> = FURNITURE_GEOMETRY;

/**
 * 가구 정의 (2026-09-21 새 가구로 교체 — 사용자 결정). 서버 items.asset_key 가 곧 가구 id 다.
 * 구성은 백엔드 V20 카탈로그와 소파·냉장고·TV 오리지널 그림이며, V24 이후 식탁·커피테이블 오리지널도 기본 지급이다.
 * 이름도 V20 값이다. 원본 에셋의 탁상 소품 10종·작은 화분 4종은 서버 상품이 아니고 앞으로도 넣지 않아 뺐다(사용자 결정 2026-09-21).
 * - 그림은 방향별로 한 장씩이다(furniture-sprites.ts). 왼쪽 벽을 등진 그림이 FRONT_RIGHT, 오른쪽 벽을 등진 그림이 FRONT_LEFT 다.
 *   두 장은 좌우 반전이 아니라 따로 렌더된 그림이라 빛·그림자 방향이 같다 — 방 꾸미기의 '방향 바꾸기'는 그림을 뒤집지 않고 바꿔 끼운다.
 * - size: 원본은 모두 같은 카메라 배율이라 한 배율로 줄인다. 씬 크기 = **원본 배율로** 잘라낸 PNG 크기 ÷ 6.3(px/씬 단위).
 *   6.3 은 2인용 소파의 긴 변이 정확히 2칸이 되는 값이고, 그때 냉장고 키가 약 1.65m 로 캐릭터(110 = 1.7m)와 비율이 맞는다.
 *   앱에 넣는 그림은 용량 때문에 2/3 로 줄인 것(4.2px/씬 단위, 빌드 스크립트 -SceneScale)이라 PNG 크기로 다시 계산하면 안 된다.
 *   씬 크기·앵커는 비율이라 그림 해상도와 무관하다. 새 가구를 잴 때는 -SceneScale 1 로 뽑아서 잰다.
 * - anchor: 접지면 무게중심의 이미지 내 비율. 이 점이 칸의 무게중심에 놓인다(grid.ts cellAnchor).
 *   상자형 가구는 맨 아래 점을 발자국 앞 꼭짓점으로 보고 좌우 끝에서 평행사변형을 복원했고,
 *   화분·소품은 바닥 쪽 띠(높이의 10% 이상)의 가운데와 그 폭으로 만든 타원의 중심을 썼다. 벽 장식은 그림 중심이다.
 * - grid: FRONT_RIGHT 기준 발자국. 잰 길이가 반 칸 경계를 0.15칸 넘게 넘으면 반 칸을 더한다. FRONT_LEFT 는 가로·세로가 바뀐다.
 * - renderSize/renderAnchor: 그림자를 포함한 PNG 표시 영역. 생성 메타데이터로 기존 contain 배율과 중심을 보존한다.
 * 같은 종류의 색상 4종은 원본 경계까지 같아서 본체 기준(SHAPES)에 한 번만 적는다. 그림자 여백이 늘어도 이 값은 바꾸지 않는다.
 */

/** 상점 선택창의 가구 분류. 서버에는 없는 클라이언트 분류이며 이름은 shop/catalog.ts 가 붙인다 */
export const FURNITURE_GROUPS = ["bed", "sofa", "table", "chair", "storage", "appliance", "wall", "decor", "rug", "plant"] as const;
export type FurnitureGroup = (typeof FURNITURE_GROUPS)[number];

/** 선택창 키처럼 밖에서 온 문자열이 가구 분류인지 (상점 가구 탭의 분류 선택창) */
export function isFurnitureGroup(value: string): value is FurnitureGroup {
  return (FURNITURE_GROUPS as readonly string[]).includes(value);
}

/** 서버 slotType. 바닥 가구는 바닥 격자, 벽 장식은 두 벽 중 한 곳에 놓인다 */
export type FurnitureSlot = "FLOOR" | "WALL";

/** 가구 한 방향의 그림 */
export type FurnitureView = {
  sprite: number;
  size: SceneSize;
  anchor: AnchorRatio;
  renderSize: SceneSize;
  renderAnchor: AnchorRatio;
};

export type FurnitureItem = {
  id: FurnitureId;
  /** 서버 items.asset_key. GET /room·/furnitures·/shop 응답을 이 가구에 잇는다 */
  assetKey: string;
  name: string;
  group: FurnitureGroup;
  slot: FurnitureSlot;
  views: Record<PlacementDirection, FurnitureView>;
  /** 상점 타일용 축소 그림 */
  shop: number;
  /** 상점·보관함에서 기존 본체 크기와 중심을 유지하기 위한 확장 캔버스 정보 */
  shopGeometry?: SpriteGeometry;
  /**
   * FRONT_RIGHT 로 놓였을 때 차지하는 칸(반 칸 단위). 배치 스냅·겹침 판정의 근거다.
   * 바닥은 cells(가로, 깊이), 벽은 wallCells(벽 따라, 아래로) 로 적는다.
   */
  grid: GridFootprint;
  /** 러그처럼 바닥에 깔리는 것. 다른 가구와 겹쳐 놓을 수 있고 캐릭터가 밟고 지나간다(러그끼리만 겹침을 본다) */
  flat: boolean;
};

/**
 * 바닥 발자국을 칸 수로 적는다. cells(가로, 깊이). 저장 단위가 반 칸이라 1.5 처럼 반 칸 단위도 쓸 수 있다.
 * 격자의 두 축은 화면에서 기울어 있다. FRONT_RIGHT 가구의 가로(왼쪽 벽과 나란함)가 격자의 row 축,
 * 깊이(오른쪽 벽과 나란함)가 col 축이라 저장 형식(w=col, d=row)에는 바꿔 넣는다.
 */
const cells = (across: number, deep: number): GridFootprint => ({ w: deep * HALF_PER_CELL, d: across * HALF_PER_CELL });

/** 벽 칸은 col 이 벽을 따라가는 가로, row 가 세로다(바닥과 달리 축을 바꾸지 않는다) */
const wallCells = (along: number, down: number): GridFootprint => ({ w: along * HALF_PER_CELL, d: down * HALF_PER_CELL });

type ViewShape = Pick<FurnitureView, "size" | "anchor">;
const view = (width: number, height: number, x: number, y: number): ViewShape => ({ size: { width, height }, anchor: { x, y } });

type Shape = {
  group: FurnitureGroup;
  slot: FurnitureSlot;
  grid: GridFootprint;
  flat?: boolean;
  FRONT_RIGHT: ViewShape;
  FRONT_LEFT: ViewShape;
};

const floor = (group: FurnitureGroup, grid: GridFootprint, right: ViewShape, left: ViewShape): Shape => ({
  group,
  slot: "FLOOR",
  grid,
  FRONT_RIGHT: right,
  FRONT_LEFT: left,
});
const rug = (grid: GridFootprint, right: ViewShape, left: ViewShape): Shape => ({ ...floor("rug", grid, right, left), flat: true });
const wall = (group: FurnitureGroup, grid: GridFootprint, right: ViewShape, left: ViewShape): Shape => ({
  group,
  slot: "WALL",
  grid,
  FRONT_RIGHT: right,
  FRONT_LEFT: left,
});

/** 색상 4종이 있는 가구 종류 → 이름 */
const COLORED_KINDS = {
  bed: "침대",
  bookcase: "책장",
  coffee_table: "커피 테이블",
  desk: "원목 책상",
  dining_chair: "식탁 의자",
  dining_table: "식탁",
  nightstand: "협탁",
  refrigerator: "냉장고",
  sofa: "2인 소파",
  tv_set: "TV·TV장 세트",
  wardrobe: "옷장",
} as const;
type ColoredKind = keyof typeof COLORED_KINDS;

const COLORS = { black: "블랙", original: "오리지널", pink: "핑크", sunset: "선셋 팝" } as const;
type FurnitureColor = keyof typeof COLORS;

/** 한 가지뿐인 가구 → 이름. 키가 곧 asset_key 다 */
const SINGLE_ITEMS = {
  window_sky_clouds: "하늘과 구름 창문",
  decor_abstract_frame: "추상 벽액자",
  decor_arch_poster: "아치 패브릭 포스터",
  decor_botanical_frame: "식물 벽액자",
  decor_round_mirror: "둥근 벽거울",
  decor_round_wall_clock: "원형 벽시계",
  decor_wall_shelf: "벽선반",
  decor_wave_poster: "물결 패브릭 포스터",
  decor_arc_floor_lamp: "아치 플로어램프",
  decor_checker_rug: "체커 러그",
  decor_oval_rug: "타원 러그",
  plant_monstera_terracotta: "테라코타 몬스테라",
  plant_palm_blue_wave: "블루 웨이브 야자",
  plant_rubber_brass: "황동 스탠드 고무나무",
  plant_sansevieria_ivory: "세로줄 도자기 산세베리아",
} as const satisfies Partial<Record<FurnitureAssetKey, string>>;
type SingleItem = keyof typeof SINGLE_ITEMS;

/** 치수는 잘라낸 그림에서 잰 값이다(주석 맨 위 참고). view(폭, 높이, 앵커 x, 앵커 y) */
const SHAPES: Record<ColoredKind | SingleItem, Shape> = {
  bed: floor("bed", cells(1.5, 2), view(174.3, 143.3, 0.5, 0.684), view(174.3, 143.3, 0.5, 0.684)),
  sofa: floor("sofa", cells(2, 1), view(131.7, 112.2, 0.5, 0.695), view(131.7, 112.2, 0.5, 0.695)),
  coffee_table: floor("table", cells(1, 1), view(74.9, 57.8, 0.5, 0.662), view(74.9, 57.8, 0.5, 0.662)),
  desk: floor("table", cells(1.5, 1), view(108.6, 95.9, 0.5, 0.706), view(108.6, 95.9, 0.5, 0.706)),
  dining_table: floor("table", cells(1.5, 1), view(103.8, 92.9, 0.5, 0.709), view(103.8, 92.9, 0.5, 0.709)),
  dining_chair: floor("chair", cells(0.5, 0.5), view(55.2, 79.8, 0.5, 0.819), view(55.2, 79.8, 0.5, 0.819)),
  bookcase: floor("storage", cells(1, 0.5), view(59.7, 120.8, 0.5, 0.871), view(59.7, 120.8, 0.5, 0.871)),
  wardrobe: floor("storage", cells(1, 0.5), view(81.9, 147.1, 0.5, 0.855), view(81.9, 147.1, 0.5, 0.855)),
  nightstand: floor("storage", cells(0.5, 0.5), view(44.1, 48.4, 0.5, 0.762), view(44.1, 48.4, 0.5, 0.762)),
  refrigerator: floor("appliance", cells(1, 1), view(69.8, 125.9, 0.5, 0.855), view(71.6, 125.9, 0.5, 0.852)),
  tv_set: floor("appliance", cells(1.5, 0.5), view(97.1, 115.6, 0.5, 0.781), view(97.5, 115.6, 0.5, 0.781)),

  window_sky_clouds: wall("wall", wallCells(1.5, 1), view(73.7, 107.9, 0.5, 0.5), view(73.7, 107.9, 0.5, 0.5)),
  decor_abstract_frame: wall("wall", wallCells(0.5, 0.5), view(27.3, 52.7, 0.5, 0.5), view(27.3, 52.7, 0.5, 0.5)),
  decor_arch_poster: wall("wall", wallCells(0.5, 0.5), view(30.2, 60, 0.5, 0.5), view(30.2, 60.3, 0.5, 0.5)),
  decor_botanical_frame: wall("wall", wallCells(0.5, 0.5), view(24.1, 47.9, 0.5, 0.5), view(24.1, 47.9, 0.5, 0.5)),
  decor_round_mirror: wall("wall", wallCells(0.5, 0.5), view(31.4, 43.5, 0.5, 0.5), view(31.4, 43.5, 0.5, 0.5)),
  decor_round_wall_clock: wall("wall", wallCells(0.5, 0.5), view(21.3, 26, 0.5, 0.5), view(21.3, 26, 0.5, 0.5)),
  decor_wall_shelf: wall("wall", wallCells(1, 0.5), view(49.2, 36.8, 0.5, 0.5), view(49.2, 32.1, 0.5, 0.5)),
  decor_wave_poster: wall("wall", wallCells(0.5, 0.5), view(30.2, 60, 0.5, 0.5), view(30.2, 60.3, 0.5, 0.5)),

  decor_arc_floor_lamp: floor("decor", cells(1, 1), view(59.4, 106.7, 0.283, 0.917), view(52.7, 90.8, 0.256, 0.921)),

  // 러그는 평면이라 발자국이 곧 그림이고 앵커는 그림 중심이다. 타원 러그는 잰 깊이(0.65칸)가 경계라 한 칸으로 올렸다.
  decor_checker_rug: rug(cells(1.5, 1.5), view(132.1, 69.5, 0.5, 0.5), view(132.1, 69.5, 0.5, 0.5)),
  decor_oval_rug: rug(cells(1.5, 1), view(100.6, 53.3, 0.5, 0.5), view(100.6, 53.3, 0.5, 0.5)),

  plant_monstera_terracotta: floor("plant", cells(1, 1), view(47.3, 63.8, 0.527, 0.895), view(51.7, 60, 0.538, 0.887)),
  plant_palm_blue_wave: floor("plant", cells(1, 1), view(61.9, 66, 0.527, 0.905), view(63.8, 67.9, 0.484, 0.908)),
  plant_rubber_brass: floor("plant", cells(0.5, 0.5), view(33, 75.6, 0.5, 0.924), view(29.8, 76.2, 0.495, 0.925)),
  plant_sansevieria_ivory: floor("plant", cells(0.5, 0.5), view(23.2, 59.8, 0.524, 0.925), view(20, 56.2, 0.488, 0.92)),
};

/**
 * V15에서 사용한 서버 assetKey 별칭. V24 이후 fridge_default는 기존 보유자를 위한 일반 가구로 유지한다.
 * 소파·TV는 이 별칭으로, 식탁·커피테이블은 *_original 키로 기본 지급한다. 비판매 키는 api/mocks/shop.ts에서 관리한다.
 */
const DEFAULT_ITEMS = {
  sofa_default: { name: "소파", kind: "sofa", sprites: FURNITURE_SPRITES.sofa_original },
  fridge_default: { name: "냉장고", kind: "refrigerator", sprites: FURNITURE_SPRITES.refrigerator_original },
  tv_default: { name: "TV", kind: "tv_set", sprites: FURNITURE_SPRITES.tv_set_original },
} as const satisfies Record<string, { name: string; kind: ColoredKind; sprites: FurnitureSpriteSet }>;
export type DefaultFurnitureId = keyof typeof DEFAULT_ITEMS;

export type FurnitureId = FurnitureAssetKey | DefaultFurnitureId;

function furnitureItem(id: FurnitureId, name: string, shape: Shape, sprites: FurnitureSpriteSet, geometry?: FurnitureSpriteGeometry): FurnitureItem {
  return {
    id,
    assetKey: id,
    name,
    group: shape.group,
    slot: shape.slot,
    grid: shape.grid,
    flat: shape.flat ?? false,
    shop: sprites.shop,
    shopGeometry: geometry?.shop,
    views: {
      FRONT_RIGHT: { sprite: sprites.left, ...shape.FRONT_RIGHT, ...spriteRenderView(shape.FRONT_RIGHT.size, shape.FRONT_RIGHT.anchor, geometry?.left) },
      FRONT_LEFT: { sprite: sprites.right, ...shape.FRONT_LEFT, ...spriteRenderView(shape.FRONT_LEFT.size, shape.FRONT_LEFT.anchor, geometry?.right) },
    },
  };
}

const coloredItems = (Object.keys(COLORED_KINDS) as ColoredKind[]).flatMap((kind) =>
  (Object.keys(COLORS) as FurnitureColor[]).map((color) => {
    const id = `${kind}_${color}` as const;
    return furnitureItem(id, `${COLORED_KINDS[kind]} (${COLORS[color]})`, SHAPES[kind], FURNITURE_SPRITES[id], SPRITE_GEOMETRY[id]);
  })
);
const singleItems = (Object.keys(SINGLE_ITEMS) as SingleItem[]).map((id) =>
  furnitureItem(id, SINGLE_ITEMS[id], SHAPES[id], FURNITURE_SPRITES[id], SPRITE_GEOMETRY[id])
);
const defaultItems = (Object.keys(DEFAULT_ITEMS) as DefaultFurnitureId[]).map((id) => {
  const { name, kind, sprites } = DEFAULT_ITEMS[id];
  return furnitureItem(id, name, SHAPES[kind], sprites, SPRITE_GEOMETRY[`${kind}_original`]);
});

/** id 로 찾는 가구 정의. 모든 FurnitureId 가 들어 있는지는 catalog 테스트가 확인한다 */
export const FURNITURE = Object.fromEntries(
  [...defaultItems, ...coloredItems, ...singleItems].map((item) => [item.id, item] as const)
) as Record<FurnitureId, FurnitureItem>;

/**
 * 벽에 붙는 기능 오브젝트(예산 보드·출금 캘린더). 가구와 달리 한 장짜리 그림이라 오른쪽 벽에서만 쓰고 방향을 바꾸지 않는다
 * (캘린더는 뒤집으면 숫자가 거꾸로 된다). 편집 모드에서 자기 벽 안에서만 옮긴다(사용자 결정 2026-09-15).
 * 벽걸이는 전부 1×1 칸이고 에셋 위에 글자를 얹지 않는다 — 숫자·막대는 탭해서 여는 팝오버가 보여준다(사용자 결정 2026-09-15).
 * - sprite: Pencil AI 생성(에셋 생성 (AI) 프레임 wall-board·wall-calendar, 마젠타 키) → remove-white-bg.ps1. 임시 에셋이며 사용자가 직접 만든 이미지로 바꾼다.
 * - size: 씬 단위. 벽 한 칸(왼쪽 45×58, 오른쪽 48×63) 안에 들어가도록 폭 44 를 기준으로 PNG 비율을 지켰다.
 * - anchor: 스프라이트 중심. 이 점이 벽 칸의 중심(cellAnchor)에 놓인다.
 */
export type WallItemId = "board" | "calendar";
export type WallSurface = Exclude<Surface, "FLOOR">;
/** 방에 놓이는 모든 오브젝트 id. 배치(Placement)·선택·드래그가 이 타입으로 통한다 */
export type RoomItemId = FurnitureId | WallItemId;

export type WallItem = {
  id: WallItemId;
  name: string;
  /** 서버 items.asset_key */
  assetKey: string;
  sprite: number;
  size: SceneSize;
  anchor: AnchorRatio;
  grid: GridFootprint;
  /** 붙는 벽. 다른 벽으로는 옮기지 않는다 */
  surface: WallSurface;
};

const CENTER: AnchorRatio = { x: 0.5, y: 0.5 };
/** 벽걸이는 전부 같은 크기다(사용자 요청 2026-09-15). 생성 프레임 72×90 비율, 벽 한 칸(48×63) 안에 든다 */
const WALL_ITEM_SIZE: SceneSize = { width: 44, height: 55 };

export const WALL_ITEMS: Record<WallItemId, WallItem> = {
  board: {
    id: "board",
    assetKey: "board_default",
    name: "예산 보드",
    sprite: require("@/assets/sprites/wall/board.png"),
    size: WALL_ITEM_SIZE,
    anchor: CENTER,
    grid: wallCells(1, 1),
    surface: "WALL_RIGHT",
  },
  calendar: {
    id: "calendar",
    assetKey: "calendar_default",
    name: "출금 캘린더",
    sprite: require("@/assets/sprites/wall/calendar.png"),
    size: WALL_ITEM_SIZE,
    anchor: CENTER,
    grid: wallCells(1, 1),
    surface: "WALL_RIGHT",
  },
};

export function isWallItemId(id: RoomItemId): id is WallItemId {
  return id in WALL_ITEMS;
}

/** 벽에 거는 것인지(기능 오브젝트 + 벽 장식 가구). 바닥 가구와 면이 다르다 */
export function hangsOnWall(id: RoomItemId): boolean {
  return isWallItemId(id) || FURNITURE[id].slot === "WALL";
}

/**
 * 서버 assetKey → 방 오브젝트 id. 가구는 assetKey 가 곧 id 이고, 벽 기능 오브젝트는 board_default·calendar_default 다.
 * 모르는 키는 undefined 라 화면이 건너뛴다 (규칙 90).
 */
const ITEM_ID_BY_ASSET_KEY: Record<string, RoomItemId> = Object.fromEntries([
  ...Object.values(FURNITURE).map((item) => [item.assetKey, item.id] as const),
  ...Object.values(WALL_ITEMS).map((item) => [item.assetKey, item.id] as const),
]);

export function roomItemIdByAssetKey(assetKey: string): RoomItemId | undefined {
  return ITEM_ID_BY_ASSET_KEY[assetKey];
}

export function roomItemName(id: RoomItemId): string {
  return isWallItemId(id) ? WALL_ITEMS[id].name : FURNITURE[id].name;
}

/** 가구 분류. 카탈로그에 없는 assetKey(서버에만 있는 새 가구)와 벽 기능 오브젝트는 null 이다 */
export function furnitureGroupOf(assetKey: string): FurnitureGroup | null {
  const id = roomItemIdByAssetKey(assetKey);
  return id === undefined || isWallItemId(id) ? null : FURNITURE[id].group;
}

/** 상점·보관함 타일 그림. 가구는 축소본, 벽 기능 오브젝트는 방 그림 그대로다. 모르는 키는 null */
export function roomItemThumbnail(assetKey: string): number | null {
  const id = roomItemIdByAssetKey(assetKey);
  if (id === undefined) return null;
  return isWallItemId(id) ? WALL_ITEMS[id].sprite : FURNITURE[id].shop;
}

/** 기존 썸네일의 본체 영역. 모르는 키·벽 기능 오브젝트·미확장 에셋은 기존 contain 표시를 유지한다. */
export function roomItemThumbnailGeometry(assetKey: string): SpriteGeometry | undefined {
  const id = roomItemIdByAssetKey(assetKey);
  return id === undefined || isWallItemId(id) ? undefined : FURNITURE[id].shopGeometry;
}
