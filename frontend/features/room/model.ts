import { ContractMismatchError } from "@/lib/contract";

/**
 * 방 씬의 좌표계와 순수 함수. 씬 단위는 Pencil CharacterRoom(Plvf1) 327×404 pt 를 그대로 쓴다.
 * 기기 폭에 맞춰 scale 만 곱하므로 배치·저장 좌표는 항상 씬 단위다(픽셀 아님).
 * Reanimated 워크릿 안에서도 부르므로 순수 함수마다 "worklet" 지시자를 둔다.
 */
export const SCENE_WIDTH = 327;
export const SCENE_HEIGHT = 586;
export const SCENE_ASPECT_RATIO = SCENE_WIDTH / SCENE_HEIGHT;

export type ScenePoint = { x: number; y: number };
export type SceneSize = { width: number; height: number };
export type SceneRect = ScenePoint & SceneSize;
export type ScenePolygon = ScenePoint[];

/** 스프라이트의 기준점 비율. 기본은 발끝(가로 중앙, 세로 95%)이라 y정렬과 배치 좌표의 기준이 된다. */
export type AnchorRatio = { x: number; y: number };
export const FOOT_ANCHOR: AnchorRatio = { x: 0.5, y: 0.95 };

/**
 * 깊이 정렬 대상. painter's algorithm: layer 오름차순, 같은 layer 안에서는 기준점 y(발끝) 오름차순으로 그린다.
 * 화면 아래쪽(y 큰 값)에 있는 것이 앞에 오므로 나중에 그려 앞을 가린다.
 * layer 는 소파처럼 캐릭터가 앞뒤로 걸치는 가구를 위한 보정값이며 기본 0 이다.
 */
export type DepthEntity = { anchor: ScenePoint; layer?: number };

export function getSceneScale(canvasWidth: number): number {
  "worklet";
  return canvasWidth / SCENE_WIDTH;
}

export function getCanvasSize(canvasWidth: number): SceneSize {
  "worklet";
  return { width: canvasWidth, height: canvasWidth / SCENE_ASPECT_RATIO };
}

/**
 * 주어진 영역(탭바 위 화면 전체 등)을 방 씬으로 빈틈 없이 채우는 캔버스 폭 (2026-09-18 코치 피드백).
 * 영역이 씬(327:404)보다 세로로 길면 폭이 영역보다 넓어지고, 넘치는 좌우는 부모가 잘라 낸다 — cover 맞춤이다.
 */
export function coverSceneWidth(boxWidth: number, boxHeight: number): number {
  return Math.max(boxWidth, Math.round(boxHeight * SCENE_ASPECT_RATIO));
}

/**
 * 주어진 영역 안에 방 전체가 들어가는 캔버스 폭 (contain 맞춤).
 * 방 꾸미기 화면처럼 바닥이 전부 보여야 끌어다 놓을 수 있는 화면에서 쓴다 — 홈의 coverSceneWidth 와 반대다.
 */
export function containSceneWidth(boxWidth: number, boxHeight: number): number {
  return Math.min(boxWidth, Math.round(boxHeight * SCENE_ASPECT_RATIO));
}

export function clamp(value: number, min: number, max: number): number {
  "worklet";
  return Math.min(Math.max(value, min), max);
}

/**
 * 기준점(씬 단위)과 크기로 스프라이트의 좌상단 사각형을 구한다. anchorRatio 를 생략하면 발끝(FOOT_ANCHOR)이다.
 * 기본값을 인자 자리(`anchorRatio = FOOT_ANCHOR`)에 두면 안 된다 — worklet 이 캡처한 바깥 값은 함수 본문 안에서만 보이는데
 * 기본 인자는 본문보다 먼저 평가돼, UI 스레드에서 "Property 'FOOT_ANCHOR' doesn't exist" 로 앱이 죽는다(2026-09-21 preview APK,
 * 인자를 생략하는 CharacterSprite 가 매 프레임 부른다). worklet 의 기본 인자에는 리터럴이나 다른 인자만 쓴다.
 */
export function getSpriteRect(anchor: ScenePoint, size: SceneSize, anchorRatio?: AnchorRatio): SceneRect {
  "worklet";
  const ratio = anchorRatio ?? FOOT_ANCHOR;
  return {
    x: anchor.x - size.width * ratio.x,
    y: anchor.y - size.height * ratio.y,
    width: size.width,
    height: size.height,
  };
}

/** 벽 오브젝트 아래에 팝오버를 붙일 좌상단(씬 단위). 오브젝트가 어디로 옮겨져도 팝오버는 씬 폭 안에 남는다 */
export function popoverBelow(rect: SceneRect, width: number, gap = 8): ScenePoint {
  return { x: clamp(rect.x, 0, SCENE_WIDTH - width), y: rect.y + rect.height + gap };
}

/** 씬 단위 사각형을 캔버스 픽셀 사각형으로 바꾼다. */
export function sceneRectToCanvas(rect: SceneRect, scale: number): SceneRect {
  "worklet";
  return { x: rect.x * scale, y: rect.y * scale, width: rect.width * scale, height: rect.height * scale };
}

/**
 * 방 씬 카메라. 화면에 그릴 때 점을 scale 로 키운 뒤 tx·ty 만큼 옮긴다(= [translate, scale] 순서의 변환).
 * Skia Group 과 RN 오버레이가 같은 값을 읽어 같은 변환을 적용하므로, 배치·저장 좌표는 카메라와 무관하게 씬 단위로 남는다.
 */
export type Camera = { scale: number; tx: number; ty: number };
export const MIN_ZOOM = 1;
export const MAX_ZOOM = 2;

/** 확대해도 방 바깥(캔버스 밖 여백)이 드러나지 않도록 배율과 평행이동을 가둔다. */
/**
 * 카메라를 "방 밖 여백이 안 보이는" 범위로 가둔다.
 * viewport 는 실제로 보이는 영역이고 생략하면 캔버스와 같다(캔버스가 화면에 딱 맞는 기존 배치 — 1배에서는 못 움직인다).
 * 홈처럼 캔버스가 화면보다 넓으면(coverSceneWidth) 캔버스가 가운데 정렬로 놓이므로 **1배에서도 넘치는 절반까지 좌우로 밀 수 있다** (2026-09-18).
 */
export function clampCamera(camera: Camera, canvas: SceneSize, viewport: SceneSize = canvas): Camera {
  "worklet";
  const scale = clamp(camera.scale, MIN_ZOOM, MAX_ZOOM);
  // 두 한계는 "내용의 끝이 화면 끝에 닿는 지점"이다. 캔버스가 화면보다 크면 가운데 정렬 때문에 그 절반만큼 양(+)으로도 밀린다.
  // 캔버스가 그 축에서 화면보다 (반올림 오차만큼이라도) 작으면 두 한계가 뒤집히므로 Math.min/max 로 바로잡아 0 에 묶는다.
  // (헬퍼 함수로 빼면 Reanimated 워크릿 변환에서 호출이 깨져 여기 그대로 둔다)
  const txStart = (canvas.width - viewport.width) / 2;
  const txEnd = (viewport.width + canvas.width) / 2 - canvas.width * scale;
  const tyStart = (canvas.height - viewport.height) / 2;
  const tyEnd = (viewport.height + canvas.height) / 2 - canvas.height * scale;
  return {
    scale,
    tx: clamp(camera.tx, Math.min(txEnd, txStart), Math.max(txEnd, txStart)),
    ty: clamp(camera.ty, Math.min(tyEnd, tyStart), Math.max(tyEnd, tyStart)),
  };
}

/** 확대하지 않아도 캔버스가 보이는 영역을 넘치는지. 1배에서 드래그를 켤지 가른다 */
export function overflowsViewport(canvas: SceneSize, viewport: SceneSize): boolean {
  return canvas.width > viewport.width + 0.5 || canvas.height > viewport.height + 0.5;
}

/** 캔버스의 한 점(핀치 중심)을 제자리에 둔 채 배율만 바꾼다. 가둔 결과가 아니므로 clampCamera 와 함께 쓴다. */
export function zoomAround(camera: Camera, focal: ScenePoint, nextScale: number): Camera {
  "worklet";
  const scale = clamp(nextScale, MIN_ZOOM, MAX_ZOOM);
  const ratio = scale / camera.scale;
  return {
    scale,
    tx: focal.x - (focal.x - camera.tx) * ratio,
    ty: focal.y - (focal.y - camera.ty) * ratio,
  };
}

/** 캔버스 픽셀 좌표(터치 지점)를 카메라를 되돌려 씬 좌표로 바꾼다. sceneRectToCanvas 의 역방향이다. */
export function canvasPointToScene(point: ScenePoint, camera: Camera, sceneScale: number): ScenePoint {
  "worklet";
  return {
    x: (point.x - camera.tx) / (camera.scale * sceneScale),
    y: (point.y - camera.ty) / (camera.scale * sceneScale),
  };
}

/** 깊이 정렬 키. 작을수록 먼저(뒤에) 그린다. */
export function depthKey(entity: DepthEntity): number {
  "worklet";
  return (entity.layer ?? 0) * SCENE_HEIGHT * 2 + entity.anchor.y;
}

/** painter's algorithm 순서로 정렬한 새 배열을 돌려준다(입력은 바꾸지 않는다). 키가 같으면 입력 순서를 유지한다. */
export function sortByDepth<T extends DepthEntity>(entities: readonly T[]): T[] {
  return entities
    .map((entity, index) => ({ entity, index }))
    .sort((a, b) => depthKey(a.entity) - depthKey(b.entity) || a.index - b.index)
    .map(({ entity }) => entity);
}

/**
 * 이미 정렬된 배열에서 움직이는 개체(기준점 y, layer)가 들어갈 위치를 구한다.
 * 반환값 i 는 "앞의 i개를 그린 뒤 개체를 그리고 나머지를 그린다"는 뜻이다. 워크릿에서 매 프레임 불러도 싼 선형 탐색이다.
 */
export function depthIndexAt(sortedKeys: readonly number[], anchorY: number, layer = 0): number {
  "worklet";
  const key = layer * SCENE_HEIGHT * 2 + anchorY;
  let index = 0;
  while (index < sortedKeys.length && sortedKeys[index] <= key) index++;
  return index;
}

/** 점이 다각형 안에 있는지(ray casting). 경계 위의 점은 구현상 안팎이 갈릴 수 있으므로 걷기 영역은 여유를 두고 정의한다. */
export function isPointInPolygon(point: ScenePoint, polygon: ScenePolygon): boolean {
  "worklet";
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i];
    const b = polygon[j];
    const crosses = a.y > point.y !== b.y > point.y;
    if (crosses && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

export function distance(a: ScenePoint, b: ScenePoint): number {
  "worklet";
  return Math.hypot(b.x - a.x, b.y - a.y);
}

export function rectContainsPoint(rect: SceneRect, point: ScenePoint): boolean {
  "worklet";
  return point.x >= rect.x && point.x <= rect.x + rect.width && point.y >= rect.y && point.y <= rect.y + rect.height;
}

export function getPolygonBounds(polygon: ScenePolygon): SceneRect {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of polygon) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

/** 선분 a→b 를 step 간격으로 샘플링해 다각형을 지나는지 본다. 가구 사이를 "통과"하는 경로를 거르는 용도라 근사로 충분하다. */
export function segmentCrossesPolygon(a: ScenePoint, b: ScenePoint, polygon: ScenePolygon, step = 6): boolean {
  const length = distance(a, b);
  const steps = Math.max(1, Math.ceil(length / step));
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    if (isPointInPolygon({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }, polygon)) return true;
  }
  return false;
}

/** 0 이상 1 미만의 난수를 주는 함수. 테스트에서는 고정 수열을 넣는다. */
export type Rng = () => number;

export type PickWaypointOptions = {
  from: ScenePoint;
  polygon: ScenePolygon;
  /** 발끝이 들어가면 안 되는 영역(가구 발자국). 경로가 지나가도 안 된다 */
  blocked?: readonly ScenePolygon[];
  rng?: Rng;
  /** 이 거리보다 가까운 후보는 버린다(제자리 걸음 방지) */
  minDistance?: number;
  /** 벽에서 이만큼 위쪽 점도 다각형 안에 있어야 한다(캐릭터 몸이 벽에 붙지 않게) */
  wallMargin?: number;
  /** 좌우 가장자리에서 이만큼 안쪽만 고른다(스프라이트 폭의 절반 이상이어야 화면 밖으로 안 잘린다) */
  xInset?: number;
  maxTries?: number;
};

/** 걷기 가능 영역 안에서 다음 목적지를 고른다. 조건을 만족하는 점을 못 찾으면 null. */
export function pickWaypoint({
  from,
  polygon,
  blocked = [],
  rng = Math.random,
  minDistance = 40,
  wallMargin = 12,
  xInset = 0,
  maxTries = 40,
}: PickWaypointOptions): ScenePoint | null {
  const bounds = getPolygonBounds(polygon);
  const minX = bounds.x + xInset;
  const maxX = bounds.x + bounds.width - xInset;
  if (maxX <= minX) return null;
  for (let i = 0; i < maxTries; i++) {
    const candidate = { x: minX + rng() * (maxX - minX), y: bounds.y + rng() * bounds.height };
    if (!isPointInPolygon(candidate, polygon)) continue;
    if (!isPointInPolygon({ x: candidate.x, y: candidate.y - wallMargin }, polygon)) continue;
    if (distance(from, candidate) < minDistance) continue;
    if (blocked.some((area) => isPointInPolygon(candidate, area))) continue;
    if (blocked.some((area) => segmentCrossesPolygon(from, candidate, area))) continue;
    return candidate;
  }
  return null;
}

/**
 * 고른 오브젝트 옆에 띄우는 말풍선(동작 버튼)의 좌상단. 단위는 부르는 쪽이 맞춘다(모두 캔버스 pt 든 모두 씬 단위든).
 * 기본은 오브젝트 바로 아래 가운데다 — 위에 두면 손가락이 방금 고른 가구를 가린다. 아래로 넘치면 위로 올리고,
 * 위아래 모두 자리가 없으면(화면만큼 큰 가구) 영역 안쪽 아래에 붙인다. 좌우는 영역 밖으로 나가지 않게 당긴다.
 */
export function placeBubble(target: SceneRect, bubble: SceneSize, bounds: SceneSize, gap = 8): ScenePoint {
  const centered = target.x + target.width / 2 - bubble.width / 2;
  const x = clamp(centered, gap, Math.max(gap, bounds.width - bubble.width - gap));

  const below = target.y + target.height + gap;
  if (below + bubble.height + gap <= bounds.height) return { x, y: below };
  const above = target.y - gap - bubble.height;
  if (above >= gap) return { x, y: above };
  return { x, y: Math.max(gap, bounds.height - bubble.height - gap) };
}

/** 일정 속도(씬 단위/초)로 이동할 때 걸리는 시간(ms) */
export function travelDurationMs(from: ScenePoint, to: ScenePoint, speed: number): number {
  return Math.round((distance(from, to) / speed) * 1000);
}

export function rectsIntersect(a: SceneRect, b: SceneRect): boolean {
  "worklet";
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

export type HitTarget<TId> = { id: TId; rect: SceneRect };

/** 그리는 순서(뒤→앞)로 주어진 사각형들 중 점을 포함하는 가장 앞의 것을 고른다. 없으면 null. */
export function hitTestTopmost<TId>(point: ScenePoint, targets: readonly HitTarget<TId>[]): TId | null {
  for (let i = targets.length - 1; i >= 0; i--) {
    if (rectContainsPoint(targets[i].rect, point)) return targets[i].id;
  }
  return null;
}

/* ───────────── 서버 계약: GET /room (docs/api-contract.md GAME, FR-GAM-01) ───────────── */

/** 서버 ItemSlotType (2026-09-16 Swagger 대조). 앞 6종은 아바타 착장, WALL·FLOOR 는 가구다 */
export const SLOT_TYPES = ["HEAD", "FACE", "UPPER_BODY", "LOWER_BODY", "SOCKS", "FOOTWEAR", "WALL", "FLOOR"] as const;
export type KnownSlotType = (typeof SLOT_TYPES)[number];
/** 계약에 없는 값은 UNKNOWN 으로 흡수한다 (규칙 90) */
export type SlotType = KnownSlotType | "UNKNOWN";

/** 가구를 놓을 수 있는 면. GET/PUT /room/layout 의 surface 필드 (계약 협의 중) */
export const SURFACE_TYPES = ["FLOOR", "WALL_LEFT", "WALL_RIGHT"] as const;
export type Surface = (typeof SURFACE_TYPES)[number];

/**
 * 가구가 보는 방향 (서버 placementDirection). FRONT_RIGHT 는 왼쪽 벽을 등지고 오른쪽 앞을, FRONT_LEFT 는 오른쪽 벽을 등지고 왼쪽 앞을 본다.
 * 가구 그림이 방향별로 한 장씩 있어(catalog.ts) 방 꾸미기의 '방향 바꾸기'가 둘을 오간다.
 */
export const PLACEMENT_DIRECTIONS = ["FRONT_RIGHT", "FRONT_LEFT"] as const;
export type PlacementDirection = (typeof PLACEMENT_DIRECTIONS)[number];

/**
 * GET /room 응답 (2026-09-16 Swagger 대조).
 * `theme` 과 `board` 는 서버 응답에 없다 — board 는 develop d80e569 에서 빠졌고 벽 보드 수치는 GET /budgets/current 로 받는다.
 * `furnitures` 는 설치된 가구의 씬 좌표다. 방 3단계에서 쓰고 지금은 받아만 둔다.
 */
export type RoomDto = {
  avatar: {
    equipped: { userItemId?: number; slotType: string; itemId: number; assetKey: string }[];
    reaction: { type: string; until: string } | null;
  };
  furnitures?: PlacedFurnitureDto[];
  coin: { balance: number };
  attendance: { checkedToday: boolean };
  stickers?: { count: number; total: number; removableToday: boolean };
  overEnvelopes?: number[];
};

/**
 * 설치된 가구 한 개. 좌표는 ScenePoint 와 같은 축이다 (3단계).
 * canUnplace는 단독 해제 가능 여부다. 필수 가구도 전체 배치를 저장할 때 같은 종류로 교체할 수 있다.
 */
export type PlacedFurnitureDto = {
  userFurnitureId: number;
  itemId: number;
  slotType: string;
  assetKey: string;
  placementStatus: string;
  placementDirection: string;
  positionX: number;
  positionY: number;
  layer: number;
  /** 기본 지급 상품 식별값(SOFA·TV·DINING_TABLE·COFFEE_TABLE). 그 외 상품은 null */
  defaultFurnitureType: string | null;
  furnitureType: FurnitureType | null;
  stickerAttached: boolean;
  /** 단독 해제 가능 여부. 설치된 필수 가구는 false */
  canUnplace: boolean;
};

export const FURNITURE_TYPES = ["SOFA", "TV", "DINING_TABLE", "COFFEE_TABLE"] as const;
export type FurnitureType = (typeof FURNITURE_TYPES)[number];

export type EquippedItem = { slotType: SlotType; itemId: number; assetKey: string };
/** type 값 목록은 미확정(frontend-spec §6 #2). until 은 시간대 없는 KST 문자열 */
export type AvatarReaction = { type: string; until: string };
/** removableToday는 호환용 이름이며 현재 설치된 바닥 가구에 딱지가 남아 있는지를 뜻한다. 일일 제한은 없다. */
export type RoomStickers = { count: number; total: number; removableToday: boolean };
export type StickerRemoval = { userFurnitureId: number; stickerAttached: boolean; stickers: RoomStickers };

export type Room = {
  equipped: EquippedItem[];
  /** 설치된 가구. 씬 배치로 바꾸는 것은 furniture.ts 가 한다 (3단계) */
  furnitures: PlacedFurnitureDto[];
  reaction: AvatarReaction | null;
  coinBalance: number;
  checkedInToday: boolean;
  /** P1 압류 딱지. 응답에 없으면 null */
  stickers: RoomStickers | null;
  /** 현재 확정 예산에서 지출 > 예산인 봉투 ID. 구버전 응답에 없으면 빈 배열 */
  overEnvelopeIds: number[];
};

const MONTH_KEY = /^\d{6}$/;

function isKnownSlotType(value: string): value is KnownSlotType {
  return (SLOT_TYPES as readonly string[]).includes(value);
}

export function toRoom(dto: RoomDto): Room {
  if (!Number.isSafeInteger(dto.coin.balance) || dto.coin.balance < 0) throw new ContractMismatchError("coin.balance");

  return {
    equipped: dto.avatar.equipped.map((item) => ({
      slotType: isKnownSlotType(item.slotType) ? item.slotType : "UNKNOWN",
      itemId: item.itemId,
      assetKey: item.assetKey,
    })),
    reaction: dto.avatar.reaction,
    furnitures: dto.furnitures ?? [],
    coinBalance: dto.coin.balance,
    checkedInToday: dto.attendance.checkedToday,
    stickers: dto.stickers ?? null,
    overEnvelopeIds: dto.overEnvelopes ?? [],
  };
}

/* ───────────── 서버 계약: POST /fin-coins/attendance (docs/api-contract.md GAME, FR-GAM-03) ───────────── */

/** granted 는 이번 요청에서 지급된 코인(당일 이미 출석했으면 0), balance 는 지급 후 잔액 */
export type AttendanceDto = { granted: number; balance: number };
export type Attendance = { granted: number; balance: number };

export function toAttendance(dto: AttendanceDto): Attendance {
  if (!Number.isSafeInteger(dto.granted) || dto.granted < 0) throw new ContractMismatchError("granted");
  if (!Number.isSafeInteger(dto.balance) || dto.balance < 0) throw new ContractMismatchError("balance");
  return { granted: dto.granted, balance: dto.balance };
}
