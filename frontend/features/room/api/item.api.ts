import { api, isMocked } from "@/api/client";
import { updateItemEquipmentMock, userItemListMock } from "@/api/mocks/item";
import { withMockLatency } from "@/api/mocks/latency";
import {
  toAvatarEquipment,
  toUserItems,
  type AvatarEquipmentDto,
  type EquippedAvatarItem,
  type ItemEquipmentRequest,
  type UserItem,
  type UserItemDto,
} from "@/features/room/items";
import type { KnownSlotType } from "@/features/room/model";

/**
 * GET /items — 보유 아바타 아이템 (FR-GAM-05). 보유 내역 id 오름차순이고 페이지가 없다.
 * 옷은 세트 한 벌이라 옷장이 부위로 나누지 않으므로 전체를 한 번에 받는다 — slotType 파라미터는 서버도 받지만 쓰지 않는다.
 * 오류: 400 COMMON_001 · 404 USER_001.
 */
export async function getUserItems(slotType?: KnownSlotType, signal?: AbortSignal): Promise<UserItem[]> {
  if (isMocked("room")) return toUserItems(await withMockLatency(userItemListMock(slotType), signal));
  const { data } = await api.get<UserItemDto[]>("/items", { params: { slotType }, signal });
  return toUserItems(data);
}

/**
 * PATCH /items/{userItemId} — 한 개를 입거나 벗는다. 부위는 서버가 판단해 같은 부위의 기존 아이템을 자동으로 벗긴다.
 * 같은 상태를 다시 보내도 성공하고(멱등), 응답은 바꾼 뒤의 전체 착장이다.
 * 오류: 400 COMMON_001 · 404 USER_001·ITEM_001(보유 아이템 없음).
 */
export async function updateItemEquipment(userItemId: number, request: ItemEquipmentRequest): Promise<EquippedAvatarItem[]> {
  if (isMocked("room")) return toAvatarEquipment(await withMockLatency(updateItemEquipmentMock(userItemId, request)));
  const { data } = await api.patch<AvatarEquipmentDto>(`/items/${userItemId}`, request);
  return toAvatarEquipment(data);
}
