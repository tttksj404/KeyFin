import { api, isMocked } from "@/api/client";
import { withMockLatency } from "@/api/mocks/latency";
import { coinBalanceMock, coinHistoryMock, purchaseShopItemMock, shopItemsMock } from "@/api/mocks/shop";
import {
  toCoinBalance,
  toCoinHistoryPage,
  toShopItems,
  toShopPurchase,
  type CoinBalanceDto,
  type CoinHistoryDto,
  type CoinHistoryPage,
  type ShopItem,
  type ShopItemDto,
  type ShopPurchase,
  type ShopPurchaseDto,
  type ShopPurchaseRequest,
} from "@/features/shop/model";

export type CoinHistoryPageParams = { cursor: number | null; size: number };

/** 계약 기본값(size 20)과 같다 */
export const COIN_HISTORY_PAGE_SIZE = 20;

/** GET /fin-coins?cursor=&size= — 코인 지급·사용 이력, 최신순 커서 페이지 (FR-GAM-08). 오류: 400 COMMON_001 · 404 USER_001 */
export async function getCoinHistory(page: CoinHistoryPageParams, signal?: AbortSignal): Promise<CoinHistoryPage> {
  if (isMocked("shop")) return toCoinHistoryPage(await withMockLatency(coinHistoryMock(page), signal));
  const { data } = await api.get<CoinHistoryDto>("/fin-coins", {
    params: { cursor: page.cursor ?? undefined, size: page.size },
    signal,
  });
  return toCoinHistoryPage(data);
}

/** GET /fin-coins/balance — 가장 최근 이력의 잔액. 이력이 없으면 0 */
export async function getCoinBalance(signal?: AbortSignal): Promise<number> {
  if (isMocked("shop")) return toCoinBalance(await withMockLatency(coinBalanceMock(), signal));
  const { data } = await api.get<CoinBalanceDto>("/fin-coins/balance", { signal });
  return toCoinBalance(data);
}

/**
 * GET /shop — 판매 중인 상품 전체. 상품 id 오름차순이고 페이지가 없으며, 보유한 상품도 owned 로 함께 온다 (FR-GAM-05).
 * 슬롯 필터는 서버도 받지만 상품 수가 적어 한 번에 받아 탭에서 나눈다 — 탭을 옮길 때마다 다시 부르지 않는다.
 */
export async function getShopItems(signal?: AbortSignal): Promise<ShopItem[]> {
  if (isMocked("shop")) return toShopItems(await withMockLatency(shopItemsMock(), signal));
  const { data } = await api.get<ShopItemDto[]>("/shop", { signal });
  return toShopItems(data);
}

/**
 * POST /shop/purchase — 상품 하나를 서버 가격으로 산다. 보유 내역 생성과 코인 차감은 함께 된다.
 * 오류: 409 SHOP_002(이미 보유, 추가 차감 없음) · 409 SHOP_003(코인 부족) · 400 COMMON_001/002 · 404 USER_001.
 * 구매해도 자동으로 장착·배치되지 않는다(옷장·방 꾸미기에서 따로 한다).
 */
export async function purchaseShopItem(request: ShopPurchaseRequest): Promise<ShopPurchase> {
  if (isMocked("shop")) return toShopPurchase(await withMockLatency(purchaseShopItemMock(request)));
  const { data } = await api.post<ShopPurchaseDto>("/shop/purchase", request);
  return toShopPurchase(data);
}
