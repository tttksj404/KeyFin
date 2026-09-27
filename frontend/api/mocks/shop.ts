import { ApiError } from "@/api/error";
import { acquireFurnitureMock, ownsFurnitureMock } from "@/api/mocks/furniture";
import { FURNITURE, type FurnitureGroup } from "@/features/room/catalog";
import { SHOP_FURNITURE_GROUPS } from "@/features/shop/catalog";
import type { CoinBalanceDto, CoinHistoryDto, CoinHistoryItemDto, ShopItemDto, ShopPurchaseDto, ShopPurchaseRequest } from "@/features/shop/model";
import { currentDateKey, parseKSTDateKey, toKSTDateKey } from "@/lib/date";

/**
 * GET /fin-coins · GET /fin-coins/balance 목 (백엔드 FinCoinServiceImpl, 2026-09-17).
 * 잔액은 방 목(api/mocks/room.ts)의 출석 뒤 잔액 1,260 과 같게 맞춘다 — 홈 배지와 코인 화면 숫자가 어긋나지 않게.
 * 지난 20일 치를 서버 규칙대로 쌓는다: 출석 +10(며칠 빠짐), 거래 전건 확인 +30, 월요일 주간 +200, 닷새 전 아이템 구매 -300.
 * 한 쪽(20건)을 넘겨 스크롤 끝에서 다음 쪽을 부르는지 볼 수 있다. reasonText 는 서버 FinCoinReason 문구와 같다.
 */
const BALANCE = 1260;
const HISTORY_DAYS = 20;
const DAY_MS = 24 * 60 * 60 * 1000;
const MONDAY = 1;

const REASON_TEXT: Record<string, string> = {
  ATTEND: "출석 보상",
  CONFIRM_ALL: "거래 내역 전체 확인 보상",
  WEEKLY: "주간 보상",
  MONTHLY: "월간 보상",
  PURCHASE: "아이템 구매",
};

type Grant = { daysAgo: number; reasonCode: string; delta: number };

/** 오래된 순. 같은 날은 출석 → 전건 확인 → 주간 → 구매 순으로 쌓인다 */
function grants(todayKey: string): Grant[] {
  const today = parseKSTDateKey(todayKey).getTime();
  const list: Grant[] = [];
  for (let daysAgo = HISTORY_DAYS; daysAgo >= 0; daysAgo -= 1) {
    const weekday = new Date(`${toKSTDateKey(new Date(today - daysAgo * DAY_MS))}T00:00:00Z`).getUTCDay();
    if (daysAgo % 4 !== 2) list.push({ daysAgo, reasonCode: "ATTEND", delta: 10 });
    if (daysAgo % 3 === 1) list.push({ daysAgo, reasonCode: "CONFIRM_ALL", delta: 30 });
    if (weekday === MONDAY) list.push({ daysAgo, reasonCode: "WEEKLY", delta: 200 });
    if (daysAgo === 5) list.push({ daysAgo, reasonCode: "PURCHASE", delta: -300 });
  }
  return list;
}

function build(todayKey: string): CoinHistoryItemDto[] {
  const today = parseKSTDateKey(todayKey).getTime();
  const list = grants(todayKey);
  let balance = BALANCE - list.reduce((sum, grant) => sum + grant.delta, 0);
  return list.map((grant, index) => {
    balance += grant.delta;
    return {
      id: index + 1,
      delta: grant.delta,
      balanceAfter: balance,
      reasonCode: grant.reasonCode,
      reasonText: REASON_TEXT[grant.reasonCode],
      grantDate: toKSTDateKey(new Date(today - grant.daysAgo * DAY_MS)),
    };
  });
}

/** 서버처럼 id 내림차순, cursor 보다 작은 id 만, 마지막 쪽이면 nextCursor null */
export function coinHistoryMock(page: { cursor: number | null; size: number }, todayKey: string = currentDateKey()): CoinHistoryDto {
  const sorted = build(todayKey)
    .sort((a, b) => b.id - a.id)
    .filter((item) => page.cursor === null || item.id < page.cursor);
  const items = sorted.slice(0, page.size);
  return { items, nextCursor: sorted.length > page.size ? items[items.length - 1].id : null };
}

export function coinBalanceMock(): CoinBalanceDto {
  return { balance: BALANCE - spent };
}

/**
 * GET /shop · POST /shop/purchase 목 (배포 서버 Swagger 2026-09-20).
 * 옷은 의상 세트 카탈로그(features/room/outfits.ts), 가구는 방 카탈로그(features/room/catalog.ts)의 assetKey 를 써서 화면에 그림이 나온다.
 * 옷은 세트 한 벌이라 부위로 나뉘지 않고, 서버가 세트를 UPPER_BODY 로 내려 주는 모양을 그대로 따랐다.
 * V19·V20·V24 적용 후의 구성·이름·가격이다. 판매 가구는 54종이며, V24에서 식탁·커피테이블 오리지널은 기본 지급으로 전환했다.
 * 냉장고는 기본 지급에서 제외하되 기존 판매 목록은 유지한다.
 * 보유 여부는 가구 목(api/mocks/furniture.ts)을 따른다.
 * 구매는 서버처럼 한 번만 되고(두 번째는 409 SHOP_002), 코인이 모자라면 409 SHOP_003 이다. 산 가구는 가구 목에 미설치로 들어간다.
 */
const OUTFIT_ITEMS: readonly ShopItemDto[] = [
  { itemId: 1, itemCategory: "AVATAR", slotType: "UPPER_BODY", name: "에픽 마법사 의상 세트", price: 500, assetKey: "outfit_epic_mage", themeCode: null, owned: true },
  { itemId: 2, itemCategory: "AVATAR", slotType: "UPPER_BODY", name: "레전더리 성기사 의상 세트", price: 1000, assetKey: "outfit_legendary_paladin", themeCode: null, owned: true },
  { itemId: 3, itemCategory: "AVATAR", slotType: "UPPER_BODY", name: "신화 용염 의상 세트", price: 2000, assetKey: "outfit_mythic_dragon", themeCode: null, owned: false },
];

/**
 * 분류별 가격(코인). 백엔드 V20 값이다 — 큰 가구 500 · 벽 장식 300 · 식물·러그·조명 200.
 * V20 은 상품마다 가격을 적지만 같은 분류는 값이 같아 분류로 묶어 둔다. 어긋나면 shop 모델 테스트가 잡는다.
 */
export const FURNITURE_PRICE_BY_GROUP: Record<FurnitureGroup, number> = {
  bed: 500,
  sofa: 500,
  appliance: 500,
  storage: 500,
  table: 500,
  chair: 500,
  wall: 300,
  rug: 200,
  plant: 200,
  decor: 200,
};

/** 기본 지급 상품·중복 그림 및 기존 비판매 냉장고 */
const NOT_FOR_SALE = new Set<string>(["sofa_default", "fridge_default", "tv_default", "sofa_original", "refrigerator_original", "tv_set_original", "dining_table_original", "coffee_table_original"]);
const FIRST_FURNITURE_ITEM_ID = 101;

/** 판매 가구. 선택창 분류 순서(침대 → 식물)대로 id 를 매긴다 */
const FURNITURE_ITEMS: readonly ShopItemDto[] = SHOP_FURNITURE_GROUPS.flatMap(({ group }) =>
  Object.values(FURNITURE).filter((item) => item.group === group && !NOT_FOR_SALE.has(item.id))
).map((item, index) => ({
  itemId: FIRST_FURNITURE_ITEM_ID + index,
  itemCategory: "FURNITURE",
  slotType: item.slot,
  name: item.name,
  price: FURNITURE_PRICE_BY_GROUP[item.group],
  assetKey: item.assetKey,
  themeCode: null,
  owned: false,
}));

/** 이번 실행에서 산 옷과 그만큼 빠진 코인. 잔액 목이 함께 줄어든다. 가구 보유는 가구 목이 들고 있다 */
const purchased = new Set<number>();
let spent = 0;

export function shopItemsMock(): ShopItemDto[] {
  return [
    ...OUTFIT_ITEMS.map((item) => ({ ...item, owned: item.owned || purchased.has(item.itemId) })),
    ...FURNITURE_ITEMS.map((item) => ({ ...item, owned: ownsFurnitureMock(item.assetKey) })),
  ];
}

export function purchaseShopItemMock(request: ShopPurchaseRequest): ShopPurchaseDto {
  const item = shopItemsMock().find((candidate) => candidate.itemId === request.itemId);
  if (item === undefined) throw new ApiError(400, "COMMON_001", "상품을 찾을 수 없습니다.");
  if (item.owned) throw new ApiError(409, "SHOP_002", "이미 보유한 상품입니다.");
  if (BALANCE - spent < item.price) throw new ApiError(409, "SHOP_003", "코인이 부족합니다.");

  spent += item.price;
  const isAvatar = item.itemCategory === "AVATAR";
  if (isAvatar) purchased.add(item.itemId);
  return {
    itemId: item.itemId,
    itemCategory: item.itemCategory,
    userItemId: isAvatar ? 500 + item.itemId : null,
    userFurnitureId: isAvatar ? null : acquireFurnitureMock(item.itemId, 600 + item.itemId, item.assetKey),
    price: item.price,
    balance: BALANCE - spent,
  };
}

export function resetShopMocks(): void {
  purchased.clear();
  spent = 0;
}
