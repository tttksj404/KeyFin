import { ApiError } from "@/api/error";
import type { AvatarEquipmentDto, ItemEquipmentRequest, UserItemDto } from "@/features/room/items";

/**
 * GET /items · PATCH /items/{userItemId} 목 (배포 서버 Swagger 2026-09-20).
 * 서버처럼 상태를 들고 있어서 옷장에서 갈아입고 나오면 그대로다(다른 도메인 목과 같은 방식).
 * 옷은 세트 한 벌이고 assetKey 가 스프라이트 조회 키다(features/room/outfits.ts) — 서버도 세트를 UPPER_BODY 로 내려 준다.
 * 보유 내역 id 는 목 안에서만 쓰는 번호이며 501 부터 매긴다. 상점 목(api/mocks/shop.ts)의 상품 id 와 맞춰 둔다.
 */
const SEED: readonly UserItemDto[] = [
  { userItemId: 501, itemId: 1, name: "에픽 마법사 의상 세트", slotType: "UPPER_BODY", assetKey: "outfit_epic_mage", equipped: true },
  { userItemId: 502, itemId: 2, name: "레전더리 성기사 의상 세트", slotType: "UPPER_BODY", assetKey: "outfit_legendary_paladin", equipped: false },
];

let items: UserItemDto[] | null = null;

function ensure(): UserItemDto[] {
  if (items === null) items = SEED.map((item) => ({ ...item }));
  return items;
}

/** 서버는 보유 id 오름차순으로 주고, slotType 을 주면 그 부위만 준다 */
export function userItemListMock(slotType?: string): UserItemDto[] {
  return ensure()
    .filter((item) => slotType === undefined || item.slotType === slotType)
    .map((item) => ({ ...item }));
}

/**
 * 서버처럼 부위를 보고 같은 부위의 기존 아이템을 벗긴 뒤, 바꾼 뒤의 전체 착장을 돌려준다.
 * 같은 상태를 다시 보내도 성공한다(멱등). 없는 보유 내역은 404 ITEM_001 이다.
 */
export function updateItemEquipmentMock(userItemId: number, request: ItemEquipmentRequest): AvatarEquipmentDto {
  const all = ensure();
  const target = all.find((item) => item.userItemId === userItemId);
  if (target === undefined) throw new ApiError(404, "ITEM_001", "보유한 아이템이 없습니다.");

  if (request.equipped) {
    for (const item of all) {
      if (item.slotType === target.slotType) item.equipped = item.userItemId === userItemId;
    }
  } else {
    target.equipped = false;
  }

  return {
    equipped: all
      .filter((item) => item.equipped)
      .map((item) => ({ userItemId: item.userItemId, itemId: item.itemId, slotType: item.slotType, assetKey: item.assetKey })),
  };
}

export function resetItemMocks(): void {
  items = null;
}
