import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getAccounts, setIncomeAccount } from "@/features/account/api/account.api";
import { isStaleAccountError } from "@/features/account/errors";
import { selectAuthStatus, useAuthStore } from "@/features/auth/store";

export const accountKeys = {
  all: ["account"] as const,
  list: () => [...accountKeys.all, "list"] as const,
};

export function accountsQueryOptions() {
  return queryOptions({
    queryKey: accountKeys.list(),
    queryFn: ({ signal }) => getAccounts(signal),
    staleTime: 30_000,
  });
}

/** 연결 계좌 목록. 서버 값이라 로그인해 있는 동안만 부른다 */
export function useAccounts() {
  const authStatus = useAuthStore(selectAuthStatus);
  return useQuery({ ...accountsQueryOptions(), enabled: authStatus === "authenticated" });
}

/**
 * 수입 계좌 지정. 성공하면 목록의 isIncome 이 바뀌므로 계좌 캐시를 무효화한다 (docs/api-guide.md §5).
 * 고른 계좌가 사라졌거나 해제된 오류(ACCOUNT_001·002)도 목록을 다시 받아 선택지를 서버 기준으로 맞춘다.
 */
export function useSetIncomeAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (accountId: number) => setIncomeAccount(accountId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountKeys.all }),
    onError: (error) => {
      if (isStaleAccountError(error)) void queryClient.invalidateQueries({ queryKey: accountKeys.list() });
    },
  });
}
