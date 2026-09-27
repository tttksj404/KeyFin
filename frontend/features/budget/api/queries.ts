import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { confirmBudget, createBudgetProposal, getCurrentBudget, updateEmergencyFund } from "@/features/budget/api/budget.api";
import { isAlreadyConfirmedError } from "@/features/budget/errors";
import type { Budget, EmergencyFundRequest } from "@/features/budget/model";
import { roomKeys } from "@/features/room/api/queries";
import type { KRW } from "@/lib/money";

export const budgetKeys = {
  all: ["budget"] as const,
  /** 서버가 정한 현재 주기 하나뿐이라 달 키를 두지 않는다 (GET /budgets/current) */
  current: () => [...budgetKeys.all, "current"] as const,
  proposal: (month: string) => [...budgetKeys.all, "proposal", month] as const,
};

export function currentBudgetQueryOptions() {
  return queryOptions({
    queryKey: budgetKeys.current(),
    queryFn: ({ signal }) => getCurrentBudget(signal),
    staleTime: 30_000,
    refetchOnWindowFocus: "always",
  });
}

/** 현재 주기 예산. PROPOSED 면 화면이 예산 확정 화면으로 보낸다(사용자 결정 2026-09-12) */
export function useCurrentBudget() {
  return useQuery(currentBudgetQueryOptions());
}

/**
 * 확정 화면으로 보내야 하는지. 승인 직후에는 캐시가 아직 PROPOSED 인 채로 새로 받는 중이라,
 * 그때 보내면 확정 화면이 잠깐 떴다가 다시 돌아오는 깜빡임이 생긴다(2026-09-14). 새로 받는 동안은 기다린다.
 */
export function needsConfirmation(budget: ReturnType<typeof useCurrentBudget>): boolean {
  return budget.data?.status === "PROPOSED" && !budget.isFetching;
}

/**
 * 제안은 주기에 한 번 만들어지는 값이라 화면에 머무는 동안 다시 부르지 않는다.
 * 조회가 아니라 생성(POST)이라 재시도도 하지 않는다 — 실패하면 사용자가 [다시 시도] 를 누른다.
 */
export function budgetProposalQueryOptions(month: string) {
  return queryOptions({
    queryKey: budgetKeys.proposal(month),
    queryFn: ({ signal }) => createBudgetProposal(month, signal),
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });
}

export function useBudgetProposal(month: string) {
  return useQuery(budgetProposalQueryOptions(month));
}

/**
 * 소비 분석 결과(PAGE-06 A·B)와 예산 확정 화면의 근거 표시는 분석 중 화면이 만든 제안을 캐시에서만 읽는다.
 * 제안 생성은 멱등이 아니라(같은 주기 두 번째 호출은 409 BUDGET_001) 여기서 다시 부르지 않는다.
 */
export function useCachedBudgetProposal(month: string) {
  return useQuery({ ...budgetProposalQueryOptions(month), enabled: false });
}

export type ConfirmBudgetVariables = {
  /** GET /budgets/current 의 budgetId — 승인 API 의 경로 값 */
  budgetId: number;
  entries: { envelopeId: number; amount: KRW }[];
};

/**
 * 승인 후에는 예산·방(벽 보드 잔액)이 모두 바뀌므로 현재 주기 예산과 방을 무효화한다 (docs/api-guide.md §5).
 * 이미 확정됨(BUDGET_003)은 서버에선 확정된 상태라 성공과 같이 캐시를 맞춘다 — 화면은 다음 단계로 넘긴다.
 */
export function useConfirmBudget() {
  const queryClient = useQueryClient();
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: budgetKeys.current() }),
      queryClient.invalidateQueries({ queryKey: roomKeys.all }),
    ]);

  return useMutation({
    mutationFn: ({ budgetId, entries }: ConfirmBudgetVariables) => confirmBudget(budgetId, entries),
    onSuccess: () => {
      void refresh();
    },
    onError: (error) => {
      if (isAlreadyConfirmedError(error)) void refresh();
    },
  });
}

type EmergencyFundVariables = { budgetId: number; request: EmergencyFundRequest };

/**
 * 비상금 설정 (FR-BGT-09). 응답이 곧 새 비상금 값이라 현재 주기 예산 캐시에 바로 넣는다 (docs/api-guide.md §5).
 * 가상 풀이라 봉투 잔액·이체에는 영향이 없어 다른 조회는 건드리지 않는다.
 */
export function useUpdateEmergencyFund() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ budgetId, request }: EmergencyFundVariables) => updateEmergencyFund(budgetId, request),
    retry: false,
    onSuccess: (fund) => {
      queryClient.setQueryData<Budget>(budgetKeys.current(), (old) =>
        old && old.budgetId === fund.budgetId ? { ...old, emergency: fund.emergency } : old
      );
    },
  });
}
