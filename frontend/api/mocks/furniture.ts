import { FURNITURE, isWallItemId, type FurnitureId } from "@/features/room/catalog";
import { placedFurnitureDtos, statusOfSurface, toPlacementRequest, toUserFurnitures, type UserFurnitureDto } from "@/features/room/furniture";
import type { FurnitureType, PlacedFurnitureDto, RoomStickers, StickerRemoval } from "@/features/room/model";
import { ApiError } from "@/api/error";
import { validatePlacements, type FurniturePlacementsRequest } from "@/features/room/placements";
import { DEFAULT_LAYOUT } from "@/features/room/scene";

/**
 * GET /furnitures · PUT /furnitures/placements 목.
 * 서버처럼 상태를 들고 있어서 방 꾸미기에서 옮기고 나오면 그 자리가 유지된다(다른 도메인 목과 같은 방식).
 *
 * 기본 4종은 서버 보유 가구다. 보드·캘린더는 서버 ID 없이 앱 배치에만 둔다.
 * 여기에 보관함을 볼 수 있게 산 뒤 아직 안 놓은 가구 몇 개를 더 둔다(상점 목도 이것을 '보유 중'으로 보여 준다).
 * 상점 목에서 가구를 사면 acquireFurnitureMock 이 미설치 상태로 더한다. userFurnitureId 는 목 안에서만 쓰는 번호다.
 */
const FIRST_ID = 201;

const DEFAULT_FURNITURE_TYPES: Partial<Record<FurnitureId, FurnitureType>> = {
  sofa_default: "SOFA",
  tv_default: "TV",
  dining_table_original: "DINING_TABLE",
  coffee_table_original: "COFFEE_TABLE",
};

/** V24 상품 분류를 재현한다. 실서버 응답의 종류는 클라이언트가 추측하지 않는다. */
const FURNITURE_TYPES: Partial<Record<FurnitureId, FurnitureType>> = {
  ...DEFAULT_FURNITURE_TYPES,
  sofa_black: "SOFA", sofa_pink: "SOFA", sofa_sunset: "SOFA",
  tv_set_black: "TV", tv_set_pink: "TV", tv_set_sunset: "TV",
  dining_table_black: "DINING_TABLE", dining_table_pink: "DINING_TABLE", dining_table_sunset: "DINING_TABLE",
  coffee_table_black: "COFFEE_TABLE", coffee_table_pink: "COFFEE_TABLE", coffee_table_sunset: "COFFEE_TABLE",
};

/** 산 뒤 보관함에 있는 가구(목 시작 상태). 바닥 가구·벽 장식·러그를 하나씩 넣어 꺼내 놓는 흐름을 모두 볼 수 있게 했다 */
export const MOCK_STORED_FURNITURE: readonly FurnitureId[] = ["bed_pink", "decor_checker_rug", "window_sky_clouds", "plant_monstera_terracotta"];

function seed(): UserFurnitureDto[] {
  const placed = DEFAULT_LAYOUT.filter((placement) => !isWallItemId(placement.itemId)).map((placement, index): UserFurnitureDto => {
    const item = FURNITURE[placement.itemId as FurnitureId];
    const request = toPlacementRequest(placement);
    const defaultType = isWallItemId(placement.itemId) ? undefined : DEFAULT_FURNITURE_TYPES[placement.itemId];
    return {
      userFurnitureId: FIRST_ID + index,
      itemId: index + 1,
      name: item.name,
      slotType: placement.surface === undefined ? "FLOOR" : "WALL",
      assetKey: item.assetKey,
      placed: true,
      placementStatus: statusOfSurface(placement.surface),
      placementDirection: request.placementDirection,
      positionX: request.positionX,
      positionY: request.positionY,
      layer: placement.layer ?? 0,
      defaultFurnitureType: defaultType ?? null,
      furnitureType: FURNITURE_TYPES[placement.itemId as FurnitureId] ?? null,
      stickerAttached: false,
      canUnplace: defaultType === undefined,
    };
  });
  const stored = MOCK_STORED_FURNITURE.map((id, index) => unplaced(FIRST_ID + placed.length + index, 100 + index, id));
  return [...placed, ...stored];
}

function unplaced(userFurnitureId: number, itemId: number, id: FurnitureId): UserFurnitureDto {
  const item = FURNITURE[id];
  return {
    userFurnitureId,
    itemId,
    name: item.name,
    slotType: item.slot,
    assetKey: item.assetKey,
    placed: false,
    placementStatus: null,
    placementDirection: null,
    positionX: null,
    positionY: null,
    layer: 0,
    defaultFurnitureType: null,
    furnitureType: FURNITURE_TYPES[id] ?? null,
    stickerAttached: false,
    canUnplace: true,
  };
}

let furnitures: UserFurnitureDto[] | null = null;

function ensure(): UserFurnitureDto[] {
  if (furnitures === null) furnitures = seed();
  return furnitures;
}

/** 서버는 보유 가구 id 오름차순으로 주고, slotType 을 주면 그 종류만 준다 */
export function furnitureListMock(slotType?: string): UserFurnitureDto[] {
  return ensure()
    .filter((furniture) => slotType === undefined || furniture.slotType === slotType)
    .sort((a, b) => a.userFurnitureId - b.userFurnitureId)
    .map((furniture) => ({ ...furniture }));
}

/** 상점 목의 '보유 중' 표시용 */
export function ownsFurnitureMock(assetKey: string): boolean {
  return ensure().some((furniture) => furniture.assetKey === assetKey);
}

/** 상점에서 산 가구를 미설치 상태로 보유한다(서버 UserFurniture.acquire). 카탈로그에 없는 키면 null */
export function acquireFurnitureMock(itemId: number, userFurnitureId: number, assetKey: string): number | null {
  if (!(assetKey in FURNITURE)) return null;
  ensure().push(unplaced(userFurnitureId, itemId, assetKey as FurnitureId));
  return userFurnitureId;
}

/** GET /room 의 furnitures — 설치된 것만, 배치 필드가 채워진 모양으로 */
export function placedFurnitureMock(): PlacedFurnitureDto[] {
  return placedFurnitureDtos(toUserFurnitures(ensure()));
}

/** 검증과 새 배열 작성이 모두 끝난 뒤 한 번에 반영한다. */
export function updateFurniturePlacementsMock(request: FurniturePlacementsRequest): UserFurnitureDto[] {
  const list = ensure();
  validatePlacements(request, toUserFurnitures(list));
  const stickers = new Set(list.filter((item) => item.placed && item.stickerAttached).map((item) => item.furnitureType));
  const placements = new Map(request.placements.map((placement) => [placement.userFurnitureId, placement]));
  furnitures = list.map((item): UserFurnitureDto => {
    const placement = placements.get(item.userFurnitureId);
    return placement ? { ...item, ...placement, placed: true, canUnplace: item.furnitureType === null,
      stickerAttached: item.furnitureType !== null ? stickers.has(item.furnitureType) : item.stickerAttached }
      : { ...item, placed: false, placementStatus: null, placementDirection: null, positionX: null, positionY: null,
        layer: 0, stickerAttached: item.furnitureType === null && item.stickerAttached, canUnplace: true };
  });
  return furnitureListMock();
}

/** 테스트·개발 재시작용 */
export function resetFurnitureMocks(initial?: UserFurnitureDto[]): void {
  furnitures = initial?.map((item) => ({ ...item })) ?? null;
  appliedPeriods.clear();
}

const appliedPeriods = new Set<string>();

/** 개발·테스트에서 예산 초과 이벤트를 재현한다. 조회·배치 저장에서는 새로 부착하지 않는다. */
export function applyBudgetStickersMock(period: string): void {
  if (appliedPeriods.has(period)) return;
  appliedPeriods.add(period);
  ensure().forEach((item) => { if (item.placementStatus === "FLOOR") item.stickerAttached = true; });
}

export function stickerStatusMock(): RoomStickers {
  const installed = ensure().filter((item) => item.placementStatus === "FLOOR");
  const count = installed.filter((item) => item.stickerAttached).length;
  return { count, total: installed.length, removableToday: count > 0 };
}

export function removeStickerMock(userFurnitureId: number): StickerRemoval {
  const target = ensure().find((item) => item.userFurnitureId === userFurnitureId);
  if (!target) throw new ApiError(404, "FURNITURE_001", "보유 가구를 찾을 수 없습니다.");
  if (target.placementStatus !== "FLOOR") throw new ApiError(400, "ROOM_001", "바닥에 설치된 가구만 제거할 수 있습니다.");
  if (!target.stickerAttached) throw new ApiError(409, "ROOM_003", "부착된 딱지가 없습니다.");
  target.stickerAttached = false;
  return { userFurnitureId, stickerAttached: false, stickers: stickerStatusMock() };
}
