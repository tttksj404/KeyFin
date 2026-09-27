import { infiniteQueryOptions, queryOptions, useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";

import { COIN_HISTORY_PAGE_SIZE, getCoinBalance, getCoinHistory, getShopItems, purchaseShopItem } from "@/features/shop/api/shop.api";
import type { CoinHistoryItem, CoinHistoryPage } from "@/features/shop/model";

export const shopKeys = {
  all: ["shop"] as const,
  /** 코인 잔액·이력. 출석처럼 코인이 바뀌면 이 프리픽스로 함께 무효화한다 */
  coins: () => [...shopKeys.all, "coins"] as const,
  coinBalance: () => [...shopKeys.coins(), "balance"] as const,
  coinHistory: () => [...shopKeys.coins(), "history"] as const,
  /** 상점 상품(GET /shop). 구매하면 owned 가 바뀌므로 코인과 함께 무효화한다 */
  items: () => [...shopKeys.all, "items"] as const,
};

export function coinBalanceQueryOptions() {
  return queryOptions({
    queryKey: shopKeys.coinBalance(),
    queryFn: ({ signal }) => getCoinBalance(signal),
    staleTime: 30_000,
  });
}

export function useCoinBalance() {
  return useQuery(coinBalanceQueryOptions());
}

export function coinHistoryQueryOptions() {
  return infiniteQueryOptions({
    queryKey: shopKeys.coinHistory(),
    queryFn: ({ pageParam, signal }) => getCoinHistory({ cursor: pageParam, size: COIN_HISTORY_PAGE_SIZE }, signal),
    initialPageParam: null as number | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    staleTime: 30_000,
  });
}

/** 코인 이력(PAGE-30). 스크롤 끝에서 nextCursor 로 다음 쪽을 받는다 */
export function useCoinHistory() {
  return useInfiniteQuery(coinHistoryQueryOptions());
}

/** 받아 둔 쪽들을 한 목록으로 */
export function flattenCoinHistory(data: InfiniteData<CoinHistoryPage> | undefined): CoinHistoryItem[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}

export function shopItemsQueryOptions() {
  return queryOptions({
    queryKey: shopKeys.items(),
    queryFn: ({ signal }) => getShopItems(signal),
    staleTime: 30_000,
  });
}

/** 상점 상품(PAGE-29). 페이지가 없어 한 번에 다 받고 화면에서 슬롯 탭으로 나눈다 */
export function useShopItems() {
  return useQuery(shopItemsQueryOptions());
}

/**
 * 상품 하나를 산다 (FR-GAM-05). 코인이 빠지는 요청이라 자동 재시도하지 않는다 —
 * 같은 상품을 다시 보내면 서버가 409 SHOP_002 로 막지만, 성공했는지 모르는 채로 다시 보내지 않는 편이 낫다 (규칙 80).
 * 서버가 준 구매 직후 잔액을 잔액 캐시에 바로 넣고(화면이 응답을 기다리지 않게), 상품 목록·코인 이력은 다시 받는다.
 */
export function usePurchaseShopItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: purchaseShopItem,
    retry: false,
    onSuccess: (purchase) => {
      queryClient.setQueryData(shopKeys.coinBalance(), purchase.balance);
      void queryClient.invalidateQueries({ queryKey: shopKeys.all });
    },
  });
}
