import { ApiError, isApiError } from "@/api/error";
import { placementMatchesSlot, toPlacementRequest, validPlacementFields, type FurniturePlacementEntry, type UserFurniture } from "@/features/room/furniture";
import { FURNITURE_TYPES } from "@/features/room/model";
import type { Placement } from "@/features/room/scene";
import { ContractMismatchError } from "@/lib/contract";

export type FurniturePlacementsRequest = { placements: FurniturePlacementEntry[] };
const TYPE_NAMES = { SOFA: "소파", TV: "TV", DINING_TABLE: "식탁", COFFEE_TABLE: "커피테이블" } as const;

export function validatePlacements(request: FurniturePlacementsRequest, owned: readonly UserFurniture[]): void {
  if (request.placements.length > 100) throw new ApiError(400, "COMMON_001", "가구는 최대 100개까지 배치할 수 있어요.");
  const byId = new Map(owned.map((furniture) => [furniture.userFurnitureId, furniture]));
  const ids = new Set<number>();
  const counts = { SOFA: 0, TV: 0, DINING_TABLE: 0, COFFEE_TABLE: 0 };
  for (const placement of request.placements) {
    const id = placement.userFurnitureId;
    if (!Number.isSafeInteger(id) || id <= 0 || ids.has(id) || !validPlacementFields(placement)) {
      throw new ApiError(400, "COMMON_001", "가구 배치 정보를 확인해 주세요.");
    }
    ids.add(id);
    const furniture = byId.get(id);
    if (!furniture) throw new ApiError(404, "FURNITURE_001", "보유 가구가 변경되었어요. 방 꾸미기에 다시 들어와 주세요.");
    if (!placementMatchesSlot(placement.placementStatus, furniture.serverState.slotType)) {
      throw new ApiError(400, "FURNITURE_002", "가구를 놓을 수 있는 면을 확인해 주세요.");
    }
    if (furniture.furnitureType !== null) counts[furniture.furnitureType]++;
  }
  const invalid = FURNITURE_TYPES.filter((type) => counts[type] !== 1);
  if (invalid.length > 0) {
    throw new ApiError(409, "FURNITURE_004", `${invalid.map((type) => `${TYPE_NAMES[type]} ${counts[type]}개`).join(", ")}예요. 종류별로 1개씩 배치해 주세요.`);
  }
}

/** 렌더링에서 제외됐던 가구만 원본으로 보존한다. 직접 보관한 가구를 다시 추가하지 않는다. */
export function buildPlacementsRequest(draft: readonly Placement[], owned: readonly UserFurniture[]): FurniturePlacementsRequest {
  const placements = draft.flatMap((placement) => placement.userFurnitureId === undefined ? [] : [{
    userFurnitureId: placement.userFurnitureId, ...toPlacementRequest(placement),
  }]);
  for (const furniture of owned) {
    if (!furniture.placed || furniture.placement !== null) continue;
    if (!furniture.serverPlacement) throw new ContractMismatchError("furnitures.placement");
    placements.push({ ...furniture.serverPlacement });
  }
  const request = { placements: placements.sort((a, b) => a.userFurnitureId - b.userFurnitureId) };
  validatePlacements(request, owned);
  return request;
}

export function placementErrorMessage(error: unknown): string {
  if (error instanceof ContractMismatchError) return "가구 정보를 확인할 수 없어요. 방 꾸미기에 다시 들어와 주세요.";
  if (!isApiError(error)) return "배치를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
  switch (error.code) {
    case "FURNITURE_004": return error.message;
    case "FURNITURE_001": return "보유 가구가 변경되었어요. 방 꾸미기에 다시 들어와 주세요.";
    case "FURNITURE_002": return "가구를 놓을 수 있는 면을 확인해 주세요.";
    case "COMMON_001": case "COMMON_002": return "가구의 개수와 배치 정보를 확인해 주세요.";
    case "NETWORK": case "TIMEOUT": return "배치를 저장하지 못했어요. 연결 상태를 확인한 뒤 다시 눌러 주세요.";
    default: return "배치를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
  }
}
