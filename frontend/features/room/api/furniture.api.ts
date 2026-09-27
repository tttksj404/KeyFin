import { api, isMocked } from "@/api/client";
import { furnitureListMock, updateFurniturePlacementsMock } from "@/api/mocks/furniture";
import { withMockLatency } from "@/api/mocks/latency";
import {
  toUserFurnitures,
  type UserFurniture,
  type UserFurnitureDto,
} from "@/features/room/furniture";
import type { FurniturePlacementsRequest } from "@/features/room/placements";

/** 가구 종류. 방 배치는 바닥·벽 둘뿐이고 아바타 아이템은 /items 가 따로 준다 */
export type FurnitureSlotType = "FLOOR" | "WALL";

/**
 * GET /furnitures — 보유 가구와 배치 상태 (docs/api-contract.md GAME, 방 3단계).
 * 보유 가구 id 오름차순이며 미설치 가구와 화면에 그릴 수 없는 가구도 함께 보존한다.
 */
export async function getFurnitures(slotType?: FurnitureSlotType, signal?: AbortSignal): Promise<UserFurniture[]> {
  if (isMocked("room")) return toUserFurnitures(await withMockLatency(furnitureListMock(slotType), signal));
  const { data } = await api.get<UserFurnitureDto[]>("/furnitures", { params: { slotType }, signal });
  return toUserFurnitures(data);
}

/** 최종 설치 가구 전체를 원자적으로 저장한다. 응답은 미설치 가구를 포함한 전체 보유 목록이다. */
export async function updateFurniturePlacements(request: FurniturePlacementsRequest): Promise<UserFurniture[]> {
  if (isMocked("room")) return toUserFurnitures(await withMockLatency(updateFurniturePlacementsMock(request)));
  const { data } = await api.put<UserFurnitureDto[]>("/furnitures/placements", request);
  return toUserFurnitures(data);
}
