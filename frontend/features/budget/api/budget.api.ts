import { api, isMocked } from "@/api/client";
import { confirmBudgetMock, createProposalMock, currentBudgetMock, updateEmergencyFundMock } from "@/api/mocks/budget";
import { withMockLatency } from "@/api/mocks/latency";
import {
  toBudget,
  toBudgetProposal,
  toConfirmRequest,
  toEmergencyFund,
  type Budget,
  type BudgetDto,
  type BudgetProposal,
  type BudgetProposalDto,
  type ConfirmBudgetResponseDto,
  type EmergencyFund,
  type EmergencyFundRequest,
  type EmergencyFundResponseDto,
} from "@/features/budget/model";
import type { KRW } from "@/lib/money";

/**
 * GET /budgets/current — 현재 주기 예산과 전체·봉투별 잔액 (FR-BGT-03·04, 노션 예산·잔액 조회).
 * 주기는 서버가 정한다. 이번 주기 예산이 없으면 서버가 제안을 만들어 PROPOSED 로 주므로 "예산 없음" 상태는 없다.
 */
export async function getCurrentBudget(signal?: AbortSignal): Promise<Budget> {
  if (isMocked("budget")) return toBudget(await withMockLatency(currentBudgetMock(), signal));
  const { data } = await api.get<BudgetDto>("/budgets/current", { signal });
  return toBudget(data);
}

/**
 * POST /budgets/proposals — 예산 제안 생성 + 소비 분석 근거(월평균·basis) (FR-USR-04, FR-BGT-01). 요청 본문이 없다.
 * 대상 월은 서버가 정하고 응답 month 로 알려준다. month 인자는 캐시 키·목 전용이다.
 * 같은 주기에 예산이 이미 있으면 409 BUDGET_001 이다(노션상 의도된 동작). 그때는 GET /budgets/current 로 이미 있는 제안을 받는다.
 */
export async function createBudgetProposal(month: string, signal?: AbortSignal): Promise<BudgetProposal> {
  if (isMocked("budget")) return toBudgetProposal(await withMockLatency(createProposalMock(month), signal));
  const { data } = await api.post<BudgetProposalDto>("/budgets/proposals", undefined, { signal });
  return toBudgetProposal(data);
}

/**
 * PUT /budgets/{budgetId}/confirm — 봉투 7개 금액을 확정한다 (FR-BGT-02). 금액은 1,000원 단위.
 * 확정은 주기당 1회라 이미 확정됐으면 409 BUDGET_003 이다.
 */
export async function confirmBudget(budgetId: number, entries: { envelopeId: number; amount: KRW }[]): Promise<void> {
  const request = toConfirmRequest(entries);
  if (isMocked("budget")) {
    await withMockLatency(confirmBudgetMock(budgetId, request));
    return;
  }
  await api.put<ConfirmBudgetResponseDto>(`/budgets/${budgetId}/confirm`, request);
}

/**
 * PUT /budgets/{budgetId}/emergency — 비상금(가상 풀) 월 금액 (FR-BGT-09, P1). 0 이상 1,000원 단위이고 0 이면 해제다.
 * 예산 확정 여부와 무관하게 주기 중 언제든 바꿀 수 있다. 오류: 400 COMMON_001·BUDGET_005 · 404 BUDGET_002.
 */
export async function updateEmergencyFund(budgetId: number, request: EmergencyFundRequest): Promise<EmergencyFund> {
  if (isMocked("budget")) return toEmergencyFund(await withMockLatency(updateEmergencyFundMock(budgetId, request)));
  const { data } = await api.put<EmergencyFundResponseDto>(`/budgets/${budgetId}/emergency`, request);
  return toEmergencyFund(data);
}
