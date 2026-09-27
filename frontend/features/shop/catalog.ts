import { CalendarCheck, CalendarRange, Coins, ListChecks, Package, Shirt, ShoppingBag, Sofa, Trophy, type LucideIcon } from "lucide-react-native";

import { roomItemThumbnail, type FurnitureGroup } from "@/features/room/catalog";
import { outfitByAssetKey } from "@/features/room/outfits";
import type { CoinReason, ShopCategory, ShopSlot } from "@/features/shop/model";

/** 코인 사유별 아이콘 (Pencil PAGE-30 코인 이력 f7YQj Icon tile). 사유 코드는 계약이고 아이콘은 클라이언트 상수다 */
const COIN_REASON_ICONS: Record<CoinReason, LucideIcon> = {
  ATTEND: CalendarCheck,
  CONFIRM_ALL: ListChecks,
  WEEKLY: CalendarRange,
  MONTHLY: Trophy,
  PURCHASE: ShoppingBag,
  UNKNOWN: Coins,
};

export function coinReasonIcon(reason: CoinReason): LucideIcon {
  return COIN_REASON_ICONS[reason];
}

/**
 * 상점 선택창 이름. 슬롯 값은 계약이고 이름은 클라이언트 상수다 (PAGE-29, Pencil 시안 없음).
 * 옷은 세트 한 벌이라 부위로 고르지 않으므로(features/room/outfits.ts) 아바타 부위는 선택창에 나오지 않는다.
 * 그래도 값이 오면 이름이 필요해 남겨 두고, 부위와 상관없이 '세트'로 부른다.
 */
const SHOP_SLOT_LABELS: Record<ShopSlot, string> = {
  HEAD: "세트",
  FACE: "세트",
  UPPER_BODY: "세트",
  LOWER_BODY: "세트",
  SOCKS: "세트",
  FOOTWEAR: "세트",
  WALL: "벽",
  FLOOR: "바닥",
  UNKNOWN: "기타",
};

export function shopSlotLabel(slot: ShopSlot): string {
  return SHOP_SLOT_LABELS[slot];
}

/**
 * 가구 분류의 선택창 이름과 구역 (사용자 요청 2026-09-21 '가구 카테고리'). 순서가 곧 선택창 순서다.
 * 큰 가구는 '가구' 구역, 벽·바닥을 꾸미는 작은 것은 '꾸미기' 구역에 둔다. 분류는 방 카탈로그(features/room/catalog.ts)가 정한다.
 */
export const SHOP_FURNITURE_GROUPS: readonly { group: FurnitureGroup; label: string; section: string }[] = [
  { group: "bed", label: "침대", section: "가구" },
  { group: "sofa", label: "소파", section: "가구" },
  { group: "table", label: "테이블·책상", section: "가구" },
  { group: "chair", label: "의자", section: "가구" },
  { group: "storage", label: "수납", section: "가구" },
  { group: "appliance", label: "가전", section: "가구" },
  { group: "wall", label: "벽 장식", section: "꾸미기" },
  { group: "decor", label: "소품", section: "꾸미기" },
  { group: "rug", label: "러그", section: "꾸미기" },
  { group: "plant", label: "식물", section: "꾸미기" },
];

/** 카탈로그에 없는 assetKey 라 그림을 못 찾은 상품 자리에 대신 둘 아이콘 */
const SHOP_CATEGORY_ICONS: Record<ShopCategory, LucideIcon> = {
  AVATAR: Shirt,
  FURNITURE: Sofa,
  UNKNOWN: Package,
};

export function shopCategoryIcon(category: ShopCategory): LucideIcon {
  return SHOP_CATEGORY_ICONS[category];
}

/**
 * 상품 그림. 옷은 의상 세트 카탈로그의 상점용 그림, 가구·벽 상품은 방 카탈로그의 상점용 축소 그림을 쓴다.
 * 어느 쪽에도 없는 assetKey 면 null 이라 부르는 쪽이 아이콘으로 폴백한다.
 */
export function shopItemSprite(assetKey: string): number | null {
  const outfit = outfitByAssetKey(assetKey);
  if (outfit) return outfit.shop;
  return roomItemThumbnail(assetKey);
}
