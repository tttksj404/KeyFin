import { queryOptions, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { accountKeys } from "@/features/account/api/queries";
import { selectAuthStatus, useAuthStore } from "@/features/auth/store";
import {
  connectFinanceAccount,
  createLinks,
  getFinanceStatus,
  getLinkCandidates,
  unlinkAccount,
  unlinkCard,
} from "@/features/link/api/link.api";
import { isStaleCandidateError, needsFinanceReconnect } from "@/features/link/errors";
import type { FinanceLinkRequest, LinkAssetRef, LinkRequest } from "@/features/link/model";
import { paymentKeys } from "@/features/payment/api/queries";

export const linkKeys = {
  all: ["link"] as const,
  financeStatus: () => [...linkKeys.all, "finance-status"] as const,
  candidates: () => [...linkKeys.all, "candidates"] as const,
};

/** 연결 상태는 서버가 가진 값이라 로그인해 있는 동안만 조회한다. 온보딩 분기의 근거라 자주 다시 부르지 않는다. */
export function financeStatusQueryOptions() {
  return queryOptions({
    queryKey: linkKeys.financeStatus(),
    queryFn: ({ signal }) => getFinanceStatus(signal),
    staleTime: 5 * 60_000,
  });
}

export function useFinanceStatus() {
  const authStatus = useAuthStore(selectAuthStatus);
  return useQuery({ ...financeStatusQueryOptions(), enabled: authStatus === "authenticated" });
}

/** 연결에 성공하면 상태 조회를 다시 하지 않고 캐시에 바로 반영한다 (docs/api-guide.md §5) */
export function useConnectFinance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: FinanceLinkRequest) => connectFinanceAccount(request),
    onSuccess: (connected) => {
      if (connected) queryClient.setQueryData(linkKeys.financeStatus(), true);
    },
  });
}

/** 금융망 재연결이 필요한 오류는 다시 받아도 같으므로 재시도하지 않는다 */
const MAX_CANDIDATES_RETRY = 1;

/** 후보는 금융망 조회 결과라 화면에 들어올 때마다 새로 받는다. 연결 뒤에는 목록의 linked 가 바뀌어야 한다 */
export function useLinkCandidates() {
  const authStatus = useAuthStore(selectAuthStatus);
  return useQuery({
    queryKey: linkKeys.candidates(),
    queryFn: ({ signal }) => getLinkCandidates(signal),
    enabled: authStatus === "authenticated",
    staleTime: 0,
    retry: (failureCount, error) => !needsFinanceReconnect(error) && failureCount < MAX_CANDIDATES_RETRY,
  });
}

/**
 * 연결·해제 뒤 서버 기준으로 다시 받을 캐시 (docs/api-guide.md §5). 후보(managed)와 계좌 목록(해제하면 수입 지정도 풀림)은 항상,
 * 카드가 바뀌었으면 관리 중인 카드만 조회하는 결제 캘린더(CARD_BILL)와 카드 청구 요약도 (2026-09-17 백엔드 코드 확인).
 */
function invalidateLinkedAssets(queryClient: QueryClient, cardsChanged: boolean) {
  const keys = [linkKeys.candidates(), accountKeys.all, ...(cardsChanged ? [paymentKeys.calendar(), paymentKeys.cardBillings()] : [])];
  return Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

/**
 * 연결 성공 후 관련 캐시를 무효화해 서버 기준으로 다시 받는다.
 * 고른 항목이 후보에서 사라졌다는 오류(LINK_004·LINK_005)도 서버 안내대로 목록을 다시 받는다.
 */
export function useCreateLinks() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: LinkRequest) => createLinks(request),
    onSuccess: (_data, request) => invalidateLinkedAssets(queryClient, request.cardIds.length > 0),
    onError: (error) => {
      if (isStaleCandidateError(error)) void queryClient.invalidateQueries({ queryKey: linkKeys.candidates() });
    },
  });
}

/**
 * 연결 해제 (PAGE-32, FR-USR-05). 서버가 멱등이라 재시도해도 안전하지만, 확인 창을 거쳐 한 번만 보내고 요청 중에는 버튼을 잠근다.
 * 이미 목록에서 사라진 항목(LINK_004·LINK_005)이면 후보를 다시 받는다.
 */
export function useUnlinkAsset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ kind, id }: LinkAssetRef) => (kind === "account" ? unlinkAccount(id) : unlinkCard(id)),
    onSuccess: (_data, { kind }) => invalidateLinkedAssets(queryClient, kind === "card"),
    onError: (error) => {
      if (isStaleCandidateError(error)) void queryClient.invalidateQueries({ queryKey: linkKeys.candidates() });
    },
  });
}
