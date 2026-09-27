import {
  FURNITURE,
  WALL_ITEMS,
  isWallItemId,
  type FurnitureId,
  type FurnitureItem,
  type FurnitureView,
  type RoomItemId,
  type WallItemId,
  type WallSurface,
} from "@/features/room/catalog";
import {
  anchorToCell,
  cellAnchor,
  cellCorners,
  cellsOverlap,
  cellToScene,
  fitsOnSurface,
  halfSpan,
  HALF_PER_CELL,
  type GridCell,
  type GridFootprint,
  type SurfaceDef,
} from "@/features/room/grid";
import {
  SCENE_HEIGHT,
  SCENE_WIDTH,
  distance,
  getSpriteRect,
  isPointInPolygon,
  type PlacementDirection,
  type ScenePoint,
  type ScenePolygon,
  type SceneRect,
  type SceneSize,
  type Surface,
} from "@/features/room/model";

/**
 * 씬 배치. 좌표는 모두 씬 단위(327×586)이며 anchor 는 가구는 접지면 무게중심, 벽 오브젝트는 스프라이트 중심이다.
 * surface 가 없으면 바닥이다. 백엔드 `user_furnitures.placement_status`(FLOOR/LEFT_WALL/RIGHT_WALL)와 같은 뜻이고
 * 변환은 furniture.ts 가 한다. DEFAULT_LAYOUT 은 서버에 설치된 가구가 없을 때 쓰는 폴백이다.
 */
export type Placement = {
  itemId: RoomItemId;
  /** 서버 보유 가구 id (GET /room·/furnitures). 기본 배치 폴백에는 없어 저장 대상에서 빠진다 (3단계) */
  userFurnitureId?: number;
  anchor: ScenePoint;
  /** 깊이 보정 */
  layer?: number;
  /** 놓인 면. 생략하면 FLOOR */
  surface?: Surface;
  /** 바닥 가구가 보는 방향. 생략하면 FRONT_RIGHT. 벽 장식은 붙은 벽이 방향을 정하므로 쓰지 않는다(facingOf) */
  direction?: PlacementDirection;
};

/** 배치가 보는 방향. 벽에 걸린 것은 붙은 벽을 등진다 — 왼쪽 벽이면 FRONT_RIGHT, 오른쪽 벽이면 FRONT_LEFT 다 */
export function facingOf(placement: Placement): PlacementDirection {
  if (placement.surface === "WALL_LEFT") return "FRONT_RIGHT";
  if (placement.surface === "WALL_RIGHT") return "FRONT_LEFT";
  return placement.direction ?? "FRONT_RIGHT";
}

/** 배치를 그리고 판정하는 데 필요한 것. 가구는 방향에 따라 그림과 발자국이 바뀐다 */
export type PlacementView = FurnitureView & { grid: GridFootprint; flat: boolean };

/** 바닥 가구는 돌면 발자국의 가로·세로가 바뀐다. 벽 장식은 어느 벽에 걸어도 벽 칸 모양이 같다 */
function footprintFacing(item: FurnitureItem, facing: PlacementDirection): GridFootprint {
  if (item.slot === "WALL" || facing === "FRONT_RIGHT") return item.grid;
  return { w: item.grid.d, d: item.grid.w };
}

export function placementView(placement: Placement): PlacementView {
  if (isWallItemId(placement.itemId)) {
    const item = WALL_ITEMS[placement.itemId];
    return { sprite: item.sprite, size: item.size, anchor: item.anchor, renderSize: item.size, renderAnchor: item.anchor, grid: item.grid, flat: false };
  }
  const item = FURNITURE[placement.itemId];
  const facing = facingOf(placement);
  return { ...item.views[facing], grid: footprintFacing(item, facing), flat: item.flat };
}

/** 방향을 바꾼 배치. FRONT_RIGHT 는 생략형으로 둬서 서버에서 받은 배치와 모양이 같게 한다 */
function withDirection(placement: Placement, direction: PlacementDirection): Placement {
  const next = { ...placement };
  if (direction === "FRONT_LEFT") next.direction = direction;
  else delete next.direction;
  return next;
}


/**
 * 배치 격자를 얹는 세 면. 벽·바닥 경계선은 floor-tall.jpg 를 픽셀로 재서 얻었다(2026-09-18).
 *   좌측 벽선 y = -0.518x + 371 · 우측 벽선 y = 0.518x + 201 · 교점 (164, 286). 좌우 대칭이라 기울기 크기가 같다.
 *
 * 세 면 모두 평행사변형이다. 걸레받이선 표본이 직선으로 떨어져(64px 마다 같은 간격) 이 그림에도 원근이 사실상 없다.
 * 사영변환으로 원근을 넣으면 칸 크기가 제각각이 되어 그림과 어긋난다.
 *
 * 칸 크기는 옛 방과 같게 유지했다(col 은 x 로 48.25, row 는 x 로 -44.875) — 가구 스프라이트 크기가 이 값 기준이라
 * 바꾸면 가구가 전부 어긋난다. 대신 바닥이 깊어진 만큼 칸 수를 8×8 → 12×12 로 늘렸다.
 * 바닥 격자는 보이는 바닥 전체를 덮도록 화면 밖까지 뻗는다. 화면 밖 칸에 놓이지 않게 막는 것은 isPlaceableOnFloor 가 한다.
 */
export const SURFACES: Record<Surface, SurfaceDef> = {
  // col 은 오른쪽 벽 방향, row 는 왼쪽 벽 방향. 둘 다 화면 앞쪽으로 증가한다.
  FLOOR: {
    quad: [
      { x: 164, y: 286 },
      { x: 743, y: 586 },
      { x: 204, y: 865 },
      { x: -375, y: 565 },
    ],
    cols: 12,
    rows: 12,
  },
  // 벽은 걸레받이를 따라가는 방향이 col, 수직이 row 다. 벽면은 수직이라 행 경계는 화면에서도 수평이다.
  // 벽걸이 아이템이 1×1 칸(폭 44)이라 칸이 그보다 커야 한다. 코너가 가운데라 좌우 벽 폭이 164·163 으로 같아 둘 다 3열이다.
  // 줄 없는 바닥 그림은 벽이 더 높아(코너 y 286) 4행까지 들어간다 — 칸 약 54×71. 윗변(코너 쪽 y 2)은 화면 안에 남는 최대치다.
  WALL_LEFT: {
    quad: [
      { x: 0, y: 87 },
      { x: 164, y: 2 },
      { x: 164, y: 286 },
      { x: 0, y: 371 },
    ],
    cols: 3,
    rows: 4,
  },
  WALL_RIGHT: {
    quad: [
      { x: 164, y: 2 },
      { x: 327, y: 87 },
      { x: 327, y: 371 },
      { x: 164, y: 286 },
    ],
    cols: 3,
    rows: 4,
  },
};

/** 코너에서 벽선(바닥 격자의 뒤쪽 두 변)을 따라 x 가 주어진 값이 되는 점 */
function wallLinePoint(corner: ScenePoint, along: ScenePoint, x: number): ScenePoint {
  return { x, y: corner.y + ((x - corner.x) * (along.y - corner.y)) / (along.x - corner.x) };
}

/**
 * 바닥 다각형. 걸레받이선은 floor-tall.jpg 를 픽셀로 재서 피팅한 값이고(2026-09-18) 코너 (164,286)·화면 아래는 화면 끝이다.
 * 이 그림은 코너가 정중앙이라 좌우가 대칭이다(옛 그림은 코너가 왼쪽 41%). 바닥을 다시 만들면 SURFACES.FLOOR 와 같이 갱신한다.
 *
 * 벽 쪽 두 변은 손으로 반올림한 (0,371)·(327,371) 이 아니라 **바닥 격자(SURFACES.FLOOR.quad)의 뒤쪽 두 변을 화면 끝까지 연장**한 점이다
 * (2026-09-22 사용자 보고). 반올림한 값은 격자 벽선보다 기울기가 0.6% 가팔라, 벽에 붙인 칸의 뒤쪽 모서리가 코너에서 멀어질수록
 * 다각형 밖으로 나갔다 — 냉장고를 오른쪽 벽 3번째 타일에 붙이면 0.5pt 차이로 거부됐다. 같은 선을 쓰면 벽에 붙은 칸은 어디든 경계 위다.
 */
export const FLOOR_POLYGON: ScenePolygon = [
  wallLinePoint(SURFACES.FLOOR.quad[0], SURFACES.FLOOR.quad[3], 0),
  SURFACES.FLOOR.quad[0],
  wallLinePoint(SURFACES.FLOOR.quad[0], SURFACES.FLOOR.quad[1], SCENE_WIDTH),
  { x: SCENE_WIDTH, y: SCENE_HEIGHT },
  { x: 0, y: SCENE_HEIGHT },
];

/** 경계 위의 점은 다각형 판정에서 안팎이 갈리므로 꼭짓점을 발자국 안쪽으로 이만큼 당겨서 본다. */
const EDGE_INSET = 0.02;

/**
 * 바닥에 실제로 놓을 수 있는 자리인지. 격자가 화면 밖까지 뻗어 있으므로
 * 발자국 네 꼭짓점이 모두 보이는 바닥 안에 들어와야 한다.
 * 벽에 딱 붙인 가구는 꼭짓점이 걸레받이선 위에 놓이므로 안쪽으로 당겨 판정한다.
 */
export function isPlaceableOnFloor(cell: GridCell, footprint: GridFootprint): boolean {
  const corners = cellCorners(SURFACES.FLOOR, cell, footprint);
  const center = corners.reduce((sum, p) => ({ x: sum.x + p.x / 4, y: sum.y + p.y / 4 }), { x: 0, y: 0 });
  return corners.every((corner) =>
    isPointInPolygon(
      { x: corner.x + (center.x - corner.x) * EDGE_INSET, y: corner.y + (center.y - corner.y) * EDGE_INSET },
      FLOOR_POLYGON
    )
  );
}

/**
 * 기본 배치. 칸으로 정의하고 발끝 좌표는 격자에서 파생시킨다. 목 데이터(api/mocks/furniture.ts)도 이 배치로 시작한다.
 * 서버 기본 가구(V24: 소파·TV·식탁·커피테이블, 전부 FRONT_RIGHT)와 좌표를 맞춘다.
 * 기존 냉장고 기본 칸(0, 2)은 비워 두어 기존 사용자에게 식탁을 지급해도 겹치지 않는다.
 */
export const DEFAULT_CELLS: readonly { itemId: FurnitureId; cell: GridCell }[] = [
  { itemId: "tv_default", cell: { col: 2, row: 0 } },
  { itemId: "dining_table_original", cell: { col: 0, row: 4 } },
  { itemId: "sofa_default", cell: { col: 6, row: 4 } },
  { itemId: "coffee_table_original", cell: { col: 4, row: 6 } },
];

/**
 * 벽에 실제로 붙일 수 있는 자리인지. 스프라이트 칸의 네 꼭짓점이 모두 씬 안에 들어와야 한다.
 * 새 방(2026-09-18)은 벽 윗변을 화면 안(코너 쪽 y 10)에 두어 아홉 칸이 모두 쓸 수 있다 — 옛 방은 윗줄이 화면 밖이었다.
 * 아랫변은 걸레받이선이라 격자가 이미 막는다.
 */
export function isPlaceableOnWall(surface: WallSurface, cell: GridCell, footprint: GridFootprint): boolean {
  const def = SURFACES[surface];
  if (!fitsOnSurface(def, cell, footprint)) return false;
  return cellCorners(def, cell, footprint).every(
    (corner) => corner.x >= 0 && corner.x <= SCENE_WIDTH && corner.y >= 0 && corner.y <= SCENE_HEIGHT
  );
}

/**
 * 벽 오브젝트 기본 자리(반 칸 단위). 둘 다 오른쪽 벽 가운데 줄에 나란히 — 캘린더가 코너 쪽, 보드가 그 옆이다.
 * 2026-09-20: 캘린더를 끝 칸(col 4)에서 코너 쪽(col 0)으로 옮겼다. 홈이 방을 화면보다 넓게 그려(cover 맞춤)
 * 끝 칸은 오른쪽이 화면 밖으로 잘려 나갔다(웹 확인: 79pt 중 26pt). 두 칸 왼쪽으로 오면 둘 다 온전히 보인다.
 * 오른쪽 벽 맨 윗줄은 코너 쪽 꼭짓점이 화면 위로 나가(y -63) 놓을 수 없다.
 */
export const DEFAULT_WALL_CELLS: readonly { itemId: WallItemId; cell: GridCell }[] = [
  { itemId: "calendar", cell: { col: 0, row: 4 } },
  { itemId: "board", cell: { col: 2, row: 4 } },
];

export const DEFAULT_LAYOUT: readonly Placement[] = [
  ...DEFAULT_CELLS.map(
    ({ itemId, cell }): Placement => ({
      itemId,
      anchor: cellAnchor(SURFACES.FLOOR, cell, FURNITURE[itemId].grid),
    })
  ),
  ...DEFAULT_WALL_CELLS.map(({ itemId, cell }): Placement => {
    const item = WALL_ITEMS[itemId];
    return { itemId, surface: item.surface, anchor: cellAnchor(SURFACES[item.surface], cell, item.grid) };
  }),
];

/** 기준점이 칸 자리에서 이만큼(씬 단위) 안쪽이면 제자리로 본다. 서버가 좌표를 소수 3자리로 다듬어 생기는 차이를 흡수한다. */
const SETTLED_TOLERANCE = 0.01;

export function isPlaceableOn(surface: Surface, cell: GridCell, footprint: GridFootprint): boolean {
  return surface === "FLOOR" ? isPlaceableOnFloor(cell, footprint) : isPlaceableOnWall(surface, cell, footprint);
}

/**
 * 면 위에서 칸을 차지한 것. 겹침은 같은 면·같은 층끼리만 본다 —
 * 러그(flat)는 가구 밑에 깔리므로 가구와 겹쳐도 되고 러그끼리만 막는다.
 */
export type Occupant = { surface: Surface; flat: boolean; cell: GridCell; footprint: GridFootprint };

export function occupantOf(placement: Placement): Occupant {
  const surface = placement.surface ?? "FLOOR";
  const { grid, flat } = placementView(placement);
  return { surface, flat, footprint: grid, cell: anchorToCell(SURFACES[surface], placement.anchor, grid) };
}

export function occupantsCollide(a: Occupant, b: Occupant): boolean {
  return a.surface === b.surface && a.flat === b.flat && cellsOverlap(a.cell, a.footprint, b.cell, b.footprint);
}

/** 그 면에서 놓을 수 있는 모든 칸을 기준점에 가까운 순으로 */
function placeableCellsByDistance(surface: Surface, anchor: ScenePoint, footprint: GridFootprint): { cell: GridCell; drift: number }[] {
  const def = SURFACES[surface];
  const cells: { cell: GridCell; drift: number }[] = [];
  for (let col = 0; col + footprint.w <= def.cols * HALF_PER_CELL; col++) {
    for (let row = 0; row + footprint.d <= def.rows * HALF_PER_CELL; row++) {
      const cell = { col, row };
      if (!isPlaceableOn(surface, cell, footprint)) continue;
      cells.push({ cell, drift: distance(anchor, cellAnchor(def, cell, footprint)) });
    }
  }
  return cells.sort((a, b) => a.drift - b.drift);
}

/**
 * 서버에서 받은 배치를 지금 방의 칸에 앉힌다. 서버는 좌표만 저장하므로 옛 방(327×404, 2026-09-18 이전) 기준으로 저장된 가구는
 * 새 방에서 벽 높이에 떠 보인다 — 놓을 수 없는 자리의 가구를 가장 가까운 빈 칸으로 당긴다.
 * 이미 제자리인 것이 자리를 지키도록 덜 어긋난 것부터 앉히고, 돌려주는 순서는 입력과 같다. 앉힐 칸이 없으면 받은 그대로 둔다.
 */
export function settlePlacements(placements: readonly Placement[]): Placement[] {
  const candidates = placements.map((placement) => {
    const surface = placement.surface ?? "FLOOR";
    const { grid, flat } = placementView(placement);
    return { surface, flat, footprint: grid, cells: placeableCellsByDistance(surface, placement.anchor, grid) };
  });
  const order = candidates
    .map((candidate, index) => ({ index, drift: candidate.cells[0]?.drift ?? Infinity }))
    .sort((a, b) => a.drift - b.drift || a.index - b.index);

  const taken: Occupant[] = [];
  const settled = placements.map((placement) => ({ ...placement }));
  for (const { index } of order) {
    const { surface, flat, footprint, cells } = candidates[index];
    const free = cells.find(({ cell }) => !taken.some((other) => occupantsCollide({ surface, flat, cell, footprint }, other)));
    if (!free) continue;
    taken.push({ surface, flat, cell: free.cell, footprint });
    if (free.drift > SETTLED_TOLERANCE) settled[index].anchor = cellAnchor(SURFACES[surface], free.cell, footprint);
  }
  return settled;
}

/** 다른 것과 겹치지 않는 가장 가까운 칸의 기준점. 그 면에 빈 칸이 없으면 null */
function nearestFreeAnchor(placement: Placement, others: readonly Occupant[]): ScenePoint | null {
  const surface = placement.surface ?? "FLOOR";
  const { grid, flat } = placementView(placement);
  const spot = placeableCellsByDistance(surface, placement.anchor, grid).find(
    ({ cell }) => !others.some((other) => occupantsCollide({ surface, flat, cell, footprint: grid }, other))
  );
  return spot ? cellAnchor(SURFACES[surface], spot.cell, grid) : null;
}

/** 보관함에서 꺼낸 바닥 가구가 처음 놓일 자리를 찾는 기준점. 보이는 바닥의 가운데쯤이다 */
const FLOOR_DROP_POINT: ScenePoint = { x: 164, y: 430 };

/** 벽 가운데. 벽 장식을 처음 걸 자리를 찾는 기준점이다 */
function wallCenter(surface: WallSurface): ScenePoint {
  const span = halfSpan(SURFACES[surface]);
  return cellToScene(SURFACES[surface], { col: span.cols / 2, row: span.rows / 2 });
}

/**
 * 보관함에서 꺼낸 가구를 놓을 자리 (방 꾸미기). 바닥 가구는 방 가운데에서 가장 가까운 빈 칸에 FRONT_RIGHT 로,
 * 벽 장식은 왼쪽 벽 가운데에서 가까운 빈 칸에 건다 — 오른쪽 벽에는 보드·캘린더가 있어 왼쪽을 먼저 본다. 둘 다 차 있으면 오른쪽 벽이다.
 * 어디에도 자리가 없으면 null.
 */
export function placeNewItem(placements: readonly Placement[], itemId: FurnitureId, userFurnitureId?: number): Placement | null {
  const others = placements.map(occupantOf);
  const base: Placement = { itemId, anchor: FLOOR_DROP_POINT, ...(userFurnitureId === undefined ? {} : { userFurnitureId }) };
  if (FURNITURE[itemId].slot === "FLOOR") {
    const anchor = nearestFreeAnchor(base, others);
    return anchor ? { ...base, anchor } : null;
  }
  for (const surface of ["WALL_LEFT", "WALL_RIGHT"] as const) {
    const candidate: Placement = { ...base, surface, anchor: wallCenter(surface) };
    const anchor = nearestFreeAnchor(candidate, others);
    if (anchor) return { ...candidate, anchor };
  }
  return null;
}

/** 벽 칸을 맞은편 벽으로 옮긴 자리. 두 벽이 코너를 사이에 두고 마주 보므로 벽을 따라가는 칸 번호가 뒤집힌다 */
function mirroredWallCell(to: WallSurface, cell: GridCell, footprint: GridFootprint): GridCell {
  return { col: halfSpan(SURFACES[to]).cols - footprint.w - cell.col, row: cell.row };
}

/**
 * '방향 바꾸기' (방 꾸미기). 바닥 가구는 제자리에서 반대 방향 그림으로 돌린다 — 발자국의 가로·세로가 바뀌므로
 * 막히면 가장 가까운 빈 칸으로 비킨다. 벽 장식은 맞은편 벽의 마주 보는 자리로 옮긴다(벽 그림은 붙은 벽이 정한다).
 * 벽 기능 오브젝트(보드·캘린더)는 한 방향 그림뿐이라 돌리지 않는다. 돌릴 수 없거나 자리가 없으면 null.
 */
export function flipPlacement(placements: readonly Placement[], itemId: RoomItemId): Placement[] | null {
  const index = placements.findIndex((placement) => placement.itemId === itemId);
  if (index === -1 || isWallItemId(itemId)) return null;
  const current = placements[index];
  const others = placements.filter((_, other) => other !== index).map(occupantOf);

  let turned: Placement;
  if (current.surface === "WALL_LEFT" || current.surface === "WALL_RIGHT") {
    const target: WallSurface = current.surface === "WALL_LEFT" ? "WALL_RIGHT" : "WALL_LEFT";
    const { grid } = placementView(current);
    const from = anchorToCell(SURFACES[current.surface], current.anchor, grid);
    turned = { ...current, surface: target, anchor: cellAnchor(SURFACES[target], mirroredWallCell(target, from, grid), grid) };
  } else {
    turned = withDirection(current, facingOf(current) === "FRONT_RIGHT" ? "FRONT_LEFT" : "FRONT_RIGHT");
  }

  const anchor = nearestFreeAnchor(turned, others);
  if (!anchor) return null;
  return placements.map((placement, other) => (other === index ? { ...turned, anchor } : placement));
}

/**
 * 서버 배치에 없는 벽 오브젝트(보드·캘린더)를 기본 자리에 채운다 (사용자 결정 2026-09-20).
 * 둘은 예산 시트·결제 캘린더로 들어가는 입구라 서버 보유 여부와 무관하게 홈에 있어야 한다.
 * 기본 자리를 서버의 다른 벽 오브젝트가 차지하고 있으면 가장 가까운 빈 칸으로 비킨다. 채운 것은 userFurnitureId 가 없어 저장 대상에서 빠진다.
 */
export function withDefaultWallItems(placements: readonly Placement[]): Placement[] {
  const missing = DEFAULT_LAYOUT.filter((fallback) => isWallItemId(fallback.itemId) && !placements.some((p) => p.itemId === fallback.itemId));
  if (missing.length === 0) return placements.map((placement) => ({ ...placement }));
  return settlePlacements([...placements, ...missing]);
}

/** 배치가 바닥 가구인지(벽에 걸린 것이 아닌지). 깊이 정렬·캐릭터 경로 계산은 이것만 본다 */
export function isFloorPlacement(placement: Placement): placement is Placement & { itemId: FurnitureId } {
  return !isWallItemId(placement.itemId) && (placement.surface ?? "FLOOR") === "FLOOR";
}

/**
 * 벽 오브젝트가 지금 놓인 씬 사각형. RN 오버레이(숫자·칩)와 팝오버가 이 위에 붙는다.
 * 배치에 없으면 null — 그때는 오버레이도 그리지 않는다.
 */
export function getWallItemRect(placements: readonly Placement[], id: WallItemId): SceneRect | null {
  const placement = placements.find((p) => p.itemId === id);
  if (!placement) return null;
  const item = WALL_ITEMS[id];
  return getSpriteRect(placement.anchor, item.size, item.anchor);
}

/**
 * 가구가 바닥에서 차지하는 발자국. 캐릭터 발끝이 들어가거나 경로가 지나가면 안 되는 영역이며,
 * 배치 격자의 칸을 씬 좌표로 되돌린 평행사변형이라 배치·겹침 판정과 같은 근거를 쓴다.
 * 축 정렬 사각형으로 감싸면 실제 넓이의 두 배가 되어 캐릭터가 갈 곳을 잃는다.
 */
export function getFootprintPolygon(placement: Placement): ScenePolygon {
  const { grid } = placementView(placement);
  const cell = anchorToCell(SURFACES.FLOOR, placement.anchor, grid);
  return cellCorners(SURFACES.FLOOR, cell, grid);
}

/** 캐릭터가 피해 갈 발자국. 벽에 걸린 것과 러그(밟고 지나간다)는 빠진다 */
export function getWalkBlockers(placements: readonly Placement[]): ScenePolygon[] {
  return placements.filter((placement) => isFloorPlacement(placement) && !placementView(placement).flat).map(getFootprintPolygon);
}

/** 캐릭터 정지 이미지의 씬 단위 크기(char1-idle.png 496×756 비율) */
export const CHARACTER_SIZE: SceneSize = { width: 72, height: 110 };

/** 코치 고양이(AI 챗봇) 그림의 씬 단위 크기. coach-cat.png 는 512×512 정사각이다 */
export const COACH_CAT_SIZE: SceneSize = { width: 60, height: 60 };
/**
 * 코치 고양이 발끝 자리 — 바닥 왼쪽 앞. 기본 가구(냉장고·TV 는 위쪽, 소파는 오른쪽)와 캐릭터 출발점(164,505)을 비껴 있고,
 * 홈이 방을 화면보다 넓게 그릴 때 잘리는 좌우 폭(약 8%, 27 단위) 안쪽이다. 방 꾸미기에서 옮기는 대상이 아니다(2026-09-22).
 */
export const COACH_CAT_ANCHOR: ScenePoint = { x: 78, y: 552 };
/** 코치 고양이 그림이 놓이는 씬 사각형. 홈의 탭 영역·말풍선·첫 진입 안내가 같은 값을 쓴다 */
export const COACH_CAT_RECT: SceneRect = getSpriteRect(COACH_CAT_ANCHOR, COACH_CAT_SIZE);
/** 기울어진 고양이 머리 위. 말풍선의 왼쪽 아래 모서리를 이 점에 맞춘다. */
export const COACH_SPEECH_ANCHOR: ScenePoint = {
  x: COACH_CAT_RECT.x + COACH_CAT_RECT.width * 0.6,
  y: COACH_CAT_RECT.y,
};
/** 고양이가 떠오르는 최대 높이(씬 단위). 그림의 모션과 말풍선의 화면 여유 계산이 공유한다. */
export const COACH_CAT_FLOAT_HEIGHT = 3;
/** 고양이가 제자리 둘레를 오가는 범위(씬 단위, useCoachCatMotion 의 산책 지점과 맞춘다) */
export const COACH_CAT_STROLL_RANGE = { left: 10, right: 12, down: 3 } as const;
/** 캐릭터가 고양이를 밟고 지나가지 않게 막는 발자국. 발끝 둘레의 작은 사각형을 산책 범위만큼 넓혔다 */
export const COACH_CAT_FOOTPRINT: ScenePolygon = [
  { x: COACH_CAT_ANCHOR.x - 24 - COACH_CAT_STROLL_RANGE.left, y: COACH_CAT_ANCHOR.y - 16 },
  { x: COACH_CAT_ANCHOR.x + 24 + COACH_CAT_STROLL_RANGE.right, y: COACH_CAT_ANCHOR.y - 16 },
  { x: COACH_CAT_ANCHOR.x + 24 + COACH_CAT_STROLL_RANGE.right, y: COACH_CAT_ANCHOR.y + 6 + COACH_CAT_STROLL_RANGE.down },
  { x: COACH_CAT_ANCHOR.x - 24 - COACH_CAT_STROLL_RANGE.left, y: COACH_CAT_ANCHOR.y + 6 + COACH_CAT_STROLL_RANGE.down },
];

/** 캐릭터 이동 파라미터. 시트 없이 정지 이미지 + 코드 모션으로 "움직이는 느낌"만 낸다. */
export const CHARACTER_MOTION = {
  /** 서 있는 자리. 방 가로 정중앙이며 가구 발자국과 겹치지 않는다(2026-09-18 새 방에 맞춰 소파 앞으로 내렸다). */
  start: { x: 164, y: 505 } as ScenePoint,
  /** 씬 단위/초 */
  speed: 42,
  /** 도착 후 다음 이동까지 쉬는 시간(ms) */
  idleWaitMs: { min: 3000, max: 6000 },
  /** 이동 중 잔걸음 바운스 높이(씬 단위)와 주기(ms) */
  bob: { height: 3, periodMs: 360 },
  /** 멈춰 있을 때 호흡 스케일 폭과 주기(ms) */
  breath: { amount: 0.018, periodMs: 1700 },
  /** 다음 목적지를 고를 때 소파로 갈 확률. 나머지는 바닥의 아무 곳이다 */
  sitChance: 0.35,
  /** 소파에 앉아 있는 시간(ms) */
  sitMs: { min: 4000, max: 8000 },
} as const;

/**
 * 캐릭터 발끝이 소파 발자국의 앞 꼭짓점보다 이만큼(씬 단위) 앞에 선다.
 * 깊이 정렬이 발끝 y 기준이라 소파보다 앞에 와야 소파에 가려지지 않고 앉은 것처럼 보인다.
 */
const SEAT_FRONT_MARGIN = 4;

/**
 * 소파에 앉을 자리. 소파가 놓인 곳에서 계산하므로 방 꾸미기에서 소파를 옮기면 앉는 자리도 따라간다.
 * 소파(색상 무관)가 여럿이면 배치 순서상 첫 소파에 앉는다.
 * 소파가 없거나 앉을 자리가 바닥 밖이면 null 이고, 그때 캐릭터는 앉지 않고 걷기만 한다.
 */
export function getSeatPoint(placements: readonly Placement[]): ScenePoint | null {
  const sofa = placements.find((placement) => isFloorPlacement(placement) && FURNITURE[placement.itemId].group === "sofa");
  if (sofa === undefined) return null;

  const footprint = getFootprintPolygon(sofa);
  const frontY = footprint.reduce((max, corner) => Math.max(max, corner.y), footprint[0].y);
  const seat = { x: sofa.anchor.x, y: frontY + SEAT_FRONT_MARGIN };
  return isPointInPolygon(seat, FLOOR_POLYGON) ? seat : null;
}
