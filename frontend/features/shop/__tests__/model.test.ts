import { ApiError } from "@/api/error";
import { furnitureListMock, resetFurnitureMocks } from "@/api/mocks/furniture";
import { SEEDED_FURNITURE, SEEDED_OUTFITS } from "@/api/mocks/shop-seed";
import { coinBalanceMock, coinHistoryMock, purchaseShopItemMock, resetShopMocks, shopItemsMock } from "@/api/mocks/shop";
import {
  coinCountLabel,
  coinDeltaLabel,
  coinDeltaSpoken,
  groupCoinHistoryByDate,
  canBuyShopItem,
  hasUnknownSlotItem,
  SHOP_FURNITURE_SLOTS,
  SHOP_SLOTS,
  shopCategoryFilterKey,
  shopGroupFilterKey,
  shopGroupsWithItems,
  shopItemsForFilter,
  shopPriceLabel,
  shopSlotFilterKey,
  toCoinBalance,
  toCoinHistoryItem,
  toCoinHistoryPage,
  toShopItem,
  toShopItems,
  toShopPurchase,
  type CoinHistoryItemDto,
  type ShopItemDto,
} from "@/features/shop/model";
import { furnitureGroupOf, type FurnitureGroup } from "@/features/room/catalog";
import { shopItemSprite } from "@/features/shop/catalog";
import { ContractMismatchError } from "@/lib/contract";

const TODAY = "2026-09-17";

/** 가구 분류가 필요 없는 선택창 테스트용 */
const noGroup = () => null;

/** 계약 예시(Swagger FinCoinResponse)의 아이템 구매 */
function dto(overrides: Partial<CoinHistoryItemDto> = {}): CoinHistoryItemDto {
  return {
    id: 42,
    delta: -100,
    balanceAfter: 1250,
    reasonCode: "PURCHASE",
    reasonText: "아이템 구매",
    grantDate: "2026-09-10",
    ...overrides,
  };
}

describe("toCoinHistoryPage", () => {
  it("계약 예시를 화면 모델로 옮기고, 사유 문구는 서버 값 그대로 둔다", () => {
    const page = toCoinHistoryPage({ items: [dto()], nextCursor: null });

    expect(page).toEqual({
      items: [{ id: 42, delta: -100, balanceAfter: 1250, reason: "PURCHASE", reasonText: "아이템 구매", grantDate: "2026-09-10" }],
      nextCursor: null,
    });
  });

  it("모르는 사유 코드는 UNKNOWN 으로 흡수한다", () => {
    expect(toCoinHistoryItem(dto({ reasonCode: "EVENT", reasonText: "이벤트 보상", delta: 50 })).reason).toBe("UNKNOWN");
  });

  it("id·증감·잔액·날짜 형식이 틀리면 계약 불일치다", () => {
    expect(() => toCoinHistoryItem(dto({ id: 0 }))).toThrow(ContractMismatchError);
    expect(() => toCoinHistoryItem(dto({ delta: 1.5 }))).toThrow(ContractMismatchError);
    expect(() => toCoinHistoryItem(dto({ balanceAfter: -1 }))).toThrow(ContractMismatchError);
    expect(() => toCoinHistoryItem(dto({ grantDate: "2026-09-10T00:00:00" }))).toThrow(ContractMismatchError);
    expect(() => toCoinBalance({ balance: -5 })).toThrow(ContractMismatchError);
    expect(toCoinBalance({ balance: 0 })).toBe(0);
  });
});

describe("코인 표기", () => {
  it("수는 자릿수를 나누고, 증감은 부호를 붙이며, 읽기 문구는 적립·사용으로 말한다", () => {
    expect(coinCountLabel(1260)).toBe("1,260");
    expect(coinDeltaLabel(10)).toBe("+10");
    expect(coinDeltaLabel(-1300)).toBe("-1,300");
    expect(coinDeltaSpoken(200)).toBe("200코인 적립");
    expect(coinDeltaSpoken(-300)).toBe("300코인 사용");
  });
});

describe("groupCoinHistoryByDate", () => {
  it("서버 순서(최신순)를 유지하며 이어진 같은 지급일만 묶는다", () => {
    const items = [
      dto({ id: 5, grantDate: "2026-09-17" }),
      dto({ id: 4, grantDate: "2026-09-16" }),
      dto({ id: 3, grantDate: "2026-09-16" }),
    ].map(toCoinHistoryItem);

    expect(groupCoinHistoryByDate(items).map((group) => [group.dateKey, group.items.map((item) => item.id)])).toEqual([
      ["2026-09-17", [5]],
      ["2026-09-16", [4, 3]],
    ]);
  });
});

describe("코인 목 — 서버처럼 쪽을 나누고 잔액과 맞는다", () => {
  it("최신순 20건씩이고 마지막 쪽은 nextCursor 가 null 이다", () => {
    const first = coinHistoryMock({ cursor: null, size: 20 }, TODAY);
    const second = coinHistoryMock({ cursor: first.nextCursor, size: 20 }, TODAY);

    expect(first.items).toHaveLength(20);
    expect(first.nextCursor).not.toBeNull();
    expect(second.nextCursor).toBeNull();
    expect(Math.min(...first.items.map((item) => item.id))).toBeGreaterThan(Math.max(...second.items.map((item) => item.id)));
  });

  it("가장 최근 이력의 잔액이 잔액 조회와 같고, 이력마다 이전 잔액 + 증감이 반영 후 잔액이다", () => {
    const all = coinHistoryMock({ cursor: null, size: 100 }, TODAY).items;

    expect(all[0]).toMatchObject({ grantDate: TODAY, reasonCode: "ATTEND", delta: 10 });
    expect(all[0].balanceAfter).toBe(coinBalanceMock().balance);
    for (let index = 0; index < all.length - 1; index += 1) {
      expect(all[index].balanceAfter).toBe(all[index + 1].balanceAfter + all[index].delta);
    }
    expect(all.every((item) => item.balanceAfter >= 0)).toBe(true);
  });
});

/** 계약 예시(Swagger ShopItemResponse)의 파란 모자 */
function shopDto(overrides: Partial<ShopItemDto> = {}): ShopItemDto {
  return {
    itemId: 123,
    itemCategory: "AVATAR",
    slotType: "HEAD",
    name: "파란 모자",
    price: 100,
    assetKey: "hat_blue",
    themeCode: null,
    owned: false,
    ...overrides,
  };
}

describe("상점 상품 (GET /shop)", () => {
  it("계약 예시를 화면 모델로 바꾸고, 모르는 카테고리·슬롯은 UNKNOWN 으로 흡수한다", () => {
    expect(toShopItem(shopDto())).toEqual({
      itemId: 123,
      category: "AVATAR",
      slot: "HEAD",
      name: "파란 모자",
      price: 100,
      assetKey: "hat_blue",
      themeCode: null,
      owned: false,
    });

    const unknown = toShopItem(shopDto({ itemCategory: "PET", slotType: "TAIL" }));
    expect(unknown.category).toBe("UNKNOWN");
    expect(unknown.slot).toBe("UNKNOWN");
  });

  it("상품 id 와 가격이 계약과 다르면 계약 불일치로 막는다", () => {
    expect(() => toShopItem(shopDto({ itemId: 0 }))).toThrow(ContractMismatchError);
    expect(() => toShopItem(shopDto({ price: -1 }))).toThrow(ContractMismatchError);
    expect(() => toShopItem(shopDto({ price: 1.5 }))).toThrow(ContractMismatchError);
    expect(toShopItem(shopDto({ price: 0 })).price).toBe(0);
  });

  it("부위 목록은 서버 enum 순서대로 옷 6종 + 가구 2종이다 — 옷은 세트라 화면에서 부위로 나누지 않아도 값은 계약대로 받는다", () => {
    expect(SHOP_SLOTS).toEqual(["HEAD", "FACE", "UPPER_BODY", "LOWER_BODY", "SOCKS", "FOOTWEAR", "WALL", "FLOOR"]);
    expect(SHOP_FURNITURE_SLOTS).toEqual(["WALL", "FLOOR"]);
  });

  it("선택창 값이 종류 전체면 그 종류를, 부위면 그 부위만 서버 순서 그대로 고른다", () => {
    const items = toShopItems([
      shopDto(),
      shopDto({ itemId: 124 }),
      shopDto({ itemId: 125, slotType: "FACE" }),
      shopDto({ itemId: 126, slotType: "FLOOR", itemCategory: "FURNITURE" }),
    ]);

    expect(shopItemsForFilter(items, shopCategoryFilterKey("AVATAR"), noGroup).map((item) => item.itemId)).toEqual([123, 124, 125]);
    expect(shopItemsForFilter(items, shopCategoryFilterKey("FURNITURE"), noGroup).map((item) => item.itemId)).toEqual([126]);
    expect(shopItemsForFilter(items, shopSlotFilterKey("HEAD"), noGroup).map((item) => item.itemId)).toEqual([123, 124]);
    expect(shopItemsForFilter(items, shopSlotFilterKey("WALL"), noGroup)).toEqual([]);
  });

  it("가구 분류는 assetKey 로 찾은 분류가 같은 가구만 고르고, 분류를 모르는 가구는 '가구 전체'에만 든다", () => {
    const furniture = (itemId: number, slotType: string, assetKey: string) => shopDto({ itemId, slotType, itemCategory: "FURNITURE", assetKey });
    const items = toShopItems([
      shopDto(),
      furniture(126, "FLOOR", "bed_pink"),
      furniture(127, "WALL", "decor_round_mirror"),
      furniture(128, "FLOOR", "sofa_blue"),
    ]);
    const groups: Record<string, FurnitureGroup> = { bed_pink: "bed", decor_round_mirror: "wall" };
    const groupOf = (assetKey: string) => groups[assetKey] ?? null;

    expect(shopItemsForFilter(items, shopGroupFilterKey("bed"), groupOf).map((item) => item.itemId)).toEqual([126]);
    expect(shopItemsForFilter(items, shopGroupFilterKey("sofa"), groupOf)).toEqual([]);
    expect(shopItemsForFilter(items, shopCategoryFilterKey("FURNITURE"), groupOf).map((item) => item.itemId)).toEqual([126, 127, 128]);
    expect(shopGroupsWithItems(items, ["bed", "sofa", "wall"], groupOf)).toEqual(["bed", "wall"]);
  });

  it("모르는 부위 상품이 있을 때만 '기타' 를 붙인다", () => {
    const known = toShopItems([shopDto(), shopDto({ itemId: 126, slotType: "FLOOR", itemCategory: "FURNITURE" })]);
    expect(hasUnknownSlotItem(known)).toBe(false);

    const withUnknown = [...known, toShopItem(shopDto({ itemId: 127, slotType: "TAIL" }))];
    expect(hasUnknownSlotItem(withUnknown)).toBe(true);
    expect(shopItemsForFilter(withUnknown, shopSlotFilterKey("UNKNOWN"), noGroup).map((item) => item.itemId)).toEqual([127]);
  });

  it("보유했거나 코인이 모자라면 못 사고, 무료 상품은 잔액과 무관하게 산다", () => {
    const item = toShopItem(shopDto());
    expect(canBuyShopItem(item, 100)).toBe(true);
    expect(canBuyShopItem(item, 99)).toBe(false);
    expect(canBuyShopItem(item, undefined)).toBe(false);
    expect(canBuyShopItem(toShopItem(shopDto({ owned: true })), 1000)).toBe(false);
    expect(canBuyShopItem(toShopItem(shopDto({ price: 0 })), 0)).toBe(true);
  });

  it("가격 문구는 자릿수를 나누고 0 은 무료다", () => {
    expect(shopPriceLabel(0)).toBe("무료");
    expect(shopPriceLabel(1200)).toBe("1,200");
  });
});

describe("상점 구매 (POST /shop/purchase)", () => {
  it("아바타는 userItemId, 가구는 userFurnitureId 만 온다", () => {
    const avatar = toShopPurchase({ itemId: 123, itemCategory: "AVATAR", userItemId: 501, userFurnitureId: null, price: 100, balance: 900 });
    expect(avatar).toMatchObject({ category: "AVATAR", userItemId: 501, userFurnitureId: null, balance: 900 });

    const furniture = toShopPurchase({ itemId: 124, itemCategory: "FURNITURE", userItemId: null, userFurnitureId: 601, price: 500, balance: 400 });
    expect(furniture).toMatchObject({ category: "FURNITURE", userItemId: null, userFurnitureId: 601 });
  });

  it("잔액이 계약과 다르면 계약 불일치로 막는다", () => {
    const dtoOf = (balance: number) => ({ itemId: 123, itemCategory: "AVATAR", userItemId: 501, userFurnitureId: null, price: 100, balance });
    expect(() => toShopPurchase(dtoOf(-1))).toThrow(ContractMismatchError);
    expect(toShopPurchase(dtoOf(0)).balance).toBe(0);
  });

  it("목은 서버처럼 한 번만 팔고, 같은 상품을 다시 사면 409 SHOP_002 다", () => {
    resetShopMocks();
    const before = coinBalanceMock().balance;
    // 신화 세트(2,000)처럼 잔액보다 비싼 상품은 SHOP_003 이라 구매 흐름을 볼 수 없다 — 잔액 안에서 고른다.
    const item = shopItemsMock().find((candidate) => !candidate.owned && candidate.price > 0 && candidate.price <= before);
    if (item === undefined) throw new Error("살 수 있는 목 상품이 없다");

    const result = purchaseShopItemMock({ itemId: item.itemId });
    expect(result.balance).toBe(before - item.price);
    expect(coinBalanceMock().balance).toBe(before - item.price);
    expect(shopItemsMock().find((candidate) => candidate.itemId === item.itemId)?.owned).toBe(true);

    const codeOf = (run: () => void) => {
      try {
        run();
        return null;
      } catch (error) {
        return error instanceof ApiError ? error.code : "NOT_API_ERROR";
      }
    };
    expect(codeOf(() => purchaseShopItemMock({ itemId: item.itemId }))).toBe("SHOP_002");
    expect(codeOf(() => purchaseShopItemMock({ itemId: 9999 }))).toBe("COMMON_001");
    resetShopMocks();
  });

  it("목의 가구 상품은 모두 그림·분류가 있고, 기본 가구와 같은 그림은 팔지 않는다", () => {
    const furniture = shopItemsMock().filter((item) => item.itemCategory === "FURNITURE");

    expect(furniture).toHaveLength(54);
    expect(furniture.every((item) => shopItemSprite(item.assetKey) !== null && furnitureGroupOf(item.assetKey) !== null)).toBe(true);
    expect(furniture.map((item) => item.assetKey)).not.toEqual(expect.arrayContaining(["sofa_original"]));
    expect(furniture.map((item) => item.assetKey)).not.toEqual(expect.arrayContaining(["sofa_default"]));
    expect(furniture.map((item) => item.assetKey)).not.toEqual(expect.arrayContaining(["dining_table_original"]));
    expect(furniture.map((item) => item.assetKey)).not.toEqual(expect.arrayContaining(["coffee_table_original"]));
  });

  it("목 상품은 V24 적용 후 판매 상품과 키·이름·부위·가격이 한 행씩 같다", () => {
    const seedRow = (item: ShopItemDto) => ({ assetKey: item.assetKey, name: item.name, slotType: item.slotType, price: item.price });
    const byKey = (a: { assetKey: string }, b: { assetKey: string }) => a.assetKey.localeCompare(b.assetKey);
    const mock = shopItemsMock();

    const outfits = mock.filter((item) => item.itemCategory === "AVATAR").map(seedRow);
    const furniture = mock.filter((item) => item.itemCategory === "FURNITURE").map(seedRow);

    expect([...outfits].sort(byKey)).toEqual([...SEEDED_OUTFITS].sort(byKey));
    expect([...furniture].sort(byKey)).toEqual([...SEEDED_FURNITURE].sort(byKey));
  });

  it("서버가 파는 상품은 빠짐없이 앱에 그림이 있다 — 없으면 상점에 아이콘만 나온다", () => {
    for (const item of [...SEEDED_OUTFITS, ...SEEDED_FURNITURE]) {
      expect([item.assetKey, shopItemSprite(item.assetKey) !== null]).toEqual([item.assetKey, true]);
    }
  });

  it("가구를 사면 보관함(가구 목)에 미설치로 들어가고 상점은 보유 중으로 보여 준다", () => {
    resetShopMocks();
    resetFurnitureMocks();
    const item = shopItemsMock().find((candidate) => candidate.itemCategory === "FURNITURE" && !candidate.owned);
    if (item === undefined) throw new Error("살 수 있는 가구 목 상품이 없다");

    const result = purchaseShopItemMock({ itemId: item.itemId });

    expect(furnitureListMock().find((furniture) => furniture.userFurnitureId === result.userFurnitureId)).toMatchObject({
      assetKey: item.assetKey,
      placed: false,
      canUnplace: true,
    });
    expect(shopItemsMock().find((candidate) => candidate.itemId === item.itemId)?.owned).toBe(true);
    resetShopMocks();
    resetFurnitureMocks();
  });
});
