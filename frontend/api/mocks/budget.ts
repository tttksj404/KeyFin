import { ApiError } from "@/api/error";
import { envelopeSpendingChangesMock } from "@/api/mocks/transaction";
import type {
  BudgetDto,
  BudgetEmergencyDto,
  BudgetEnvelopeDto,
  EmergencyFundRequest,
  EmergencyFundResponseDto,
  BudgetProposalDto,
  ConfirmBudgetRequest,
  ConfirmBudgetResponseDto,
} from "@/features/budget/model";
import { currentDateKey } from "@/lib/date";

/**
 * 봉투 7종(고정 id 1~7)의 제안액과 목 지출액. 금액은 Pencil home/p0 (EWfx2) 예산 카드와 같다:
 * 총 500,000 중 320,000 사용, 180,000 남음(36%).
 */
const ENVELOPES: { envelopeId: number; name: string; proposedAmount: number; spent: number }[] = [
  { envelopeId: 1, name: "외식", proposedAmount: 100000, spent: 68000 },
  { envelopeId: 2, name: "교통비", proposedAmount: 60000, spent: 40000 },
  { envelopeId: 3, name: "의료·건강", proposedAmount: 40000, spent: 4000 },
  { envelopeId: 4, name: "취미·여가", proposedAmount: 70000, spent: 55000 },
  { envelopeId: 5, name: "쇼핑", proposedAmount: 90000, spent: 98000 },
  { envelopeId: 6, name: "편의점·마트·잡화", proposedAmount: 80000, spent: 40000 },
  { envelopeId: 7, name: "기타", proposedAmount: 60000, spent: 15000 },
];

/**
 * 최근 3개월 월평균. 합계 533,000 으로 제안 합계(500,000)보다 크다 — "분석해서 줄여 제안했다" 는 흐름이 화면에 보이게 한 값이다.
 * (Pencil budget-proposal g1fhiV 시안과 같은 수치)
 */
const MONTHLY_AVG: Record<number, number> = { 1: 112000, 2: 62000, 3: 38000, 4: 74000, 5: 105000, 6: 84000, 7: 58000 };

const MOCK_BUDGET_ID = 1;

/** 목 사용자의 기준일은 1일 — 주기 = 이번 달 1일~말일 */
function mockPeriod(todayKey: string): { month: string; periodFrom: string; periodTo: string } {
  const year = Number(todayKey.slice(0, 4));
  const month = Number(todayKey.slice(5, 7));
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const prefix = todayKey.slice(0, 7);
  return { month: `${year}${todayKey.slice(5, 7)}`, periodFrom: `${prefix}-01`, periodTo: `${prefix}-${lastDay}` };
}

/** 서버처럼 잔여율은 remaining × 100 ÷ confirmed 정수 내림(초과면 음수), 확정액 0 이면 null */
function rateOf(remaining: number, confirmed: number): number | null {
  return confirmed === 0 ? null : Math.floor((remaining * 100) / confirmed);
}

/**
 * 비상금 가상 풀. 처음은 미설정(0)이고 설정 화면에서 바꾸면 그 값이 남는다.
 * 사용액은 목에 EMERGENCY 태그 거래가 없어 0 이며, 잔액은 서버처럼 설정액 − 사용액이다.
 */
const EMERGENCY_SPENT = 0;
let emergencyAmount = 0;

function emergencyState(): BudgetEmergencyDto {
  return { amount: emergencyAmount, spent: EMERGENCY_SPENT, remaining: emergencyAmount - EMERGENCY_SPENT };
}

/** 확정 예산 응답 예시(노션 예산·잔액 조회 CONFIRMED). amounts 가 없으면 제안액을 그대로 확정한 것으로 본다 */
export function budgetConfirmedMock(todayKey: string, amounts?: Record<number, number>): BudgetDto {
  const changes = envelopeSpendingChangesMock(todayKey);
  const envelopes: BudgetEnvelopeDto[] = ENVELOPES.map(({ envelopeId, name, proposedAmount, spent: initialSpent }) => {
    const spent = initialSpent + (changes[envelopeId] ?? 0);
    const confirmed = amounts?.[envelopeId] ?? proposedAmount;
    const remaining = confirmed - spent;
    return { envelopeId, name, proposedAmount: null, confirmedAmount: confirmed, spent, remaining, remainingRate: rateOf(remaining, confirmed) };
  });
  const confirmed = envelopes.reduce((sum, envelope) => sum + (envelope.confirmedAmount ?? 0), 0);
  const spent = envelopes.reduce((sum, envelope) => sum + (envelope.spent ?? 0), 0);
  return {
    budgetId: MOCK_BUDGET_ID,
    ...mockPeriod(todayKey),
    status: "CONFIRMED",
    total: { confirmed, spent, remaining: confirmed - spent, remainingRate: rateOf(confirmed - spent, confirmed) },
    envelopes,
    emergency: emergencyState(),
  };
}

/** 확정 전 예산 응답 예시(노션 예산·잔액 조회 PROPOSED): total=null, 봉투는 제안액만 */
export function budgetProposedMock(todayKey: string): BudgetDto {
  return {
    budgetId: MOCK_BUDGET_ID,
    ...mockPeriod(todayKey),
    status: "PROPOSED",
    total: null,
    envelopes: ENVELOPES.map(({ envelopeId, name, proposedAmount }) => ({
      envelopeId,
      name,
      proposedAmount,
      confirmedAmount: null,
      spent: null,
      remaining: null,
      remainingRate: null,
    })),
    emergency: emergencyState(),
  };
}

/** POST /budgets/proposals 응답 예시 (노션 예산 제안 생성) */
export function budgetProposalMock(month: string): BudgetProposalDto {
  return {
    budgetId: MOCK_BUDGET_ID,
    month,
    status: "PROPOSED",
    basis: "최근 3개월 평균",
    envelopes: ENVELOPES.map(({ envelopeId, name, proposedAmount }) => ({
      envelopeId,
      name,
      proposedAmount,
      monthlyAvg: MONTHLY_AVG[envelopeId] ?? proposedAmount,
    })),
  };
}

/**
 * 앱이 도는 동안만 유지되는 이번 주기 예산. 서버처럼 움직인다:
 * 제안은 주기당 한 번(두 번째는 409 BUDGET_001), 조회는 없으면 제안을 만들어 PROPOSED, 확정은 한 번(두 번째는 409 BUDGET_003).
 */
let currentBudget: { month: string; status: "PROPOSED" | "CONFIRMED"; amounts?: Record<number, number> } | null = null;

export function createProposalMock(month: string): BudgetProposalDto {
  if (currentBudget?.month === month) throw new ApiError(409, "BUDGET_001", "해당 월의 예산이 이미 존재합니다.");
  currentBudget = { month, status: "PROPOSED" };
  return budgetProposalMock(month);
}

export function currentBudgetMock(todayKey: string = currentDateKey()): BudgetDto {
  const month = mockPeriod(todayKey).month;
  if (currentBudget?.month !== month) currentBudget = { month, status: "PROPOSED" };
  return currentBudget.status === "CONFIRMED" ? budgetConfirmedMock(todayKey, currentBudget.amounts) : budgetProposedMock(todayKey);
}

export function confirmBudgetMock(budgetId: number, request: ConfirmBudgetRequest, todayKey: string = currentDateKey()): ConfirmBudgetResponseDto {
  const month = mockPeriod(todayKey).month;
  if (budgetId !== MOCK_BUDGET_ID || currentBudget?.month !== month) throw new ApiError(404, "BUDGET_002", "예산을 찾을 수 없습니다.");
  if (currentBudget.status === "CONFIRMED") throw new ApiError(409, "BUDGET_003", "이미 확정된 예산은 변경할 수 없습니다.");
  currentBudget = { month, status: "CONFIRMED", amounts: Object.fromEntries(request.envelopes.map((e) => [e.envelopeId, e.amount])) };
  return { budgetId, month: mockPeriod(todayKey).month, status: "CONFIRMED" };
}

/** 온보딩을 마친 사용자로 시작할 때: 이번 주기 예산이 제안액 그대로 확정된 상태 */
export function seedConfirmedBudgetMock(todayKey: string = currentDateKey()): void {
  currentBudget = { month: mockPeriod(todayKey).month, status: "CONFIRMED" };
}

/** GET /room은 예산을 만들지 않으며 현재 확정 예산의 실제 초과만 반환한다. */
export function overEnvelopeIdsMock(todayKey: string = currentDateKey()): number[] {
  if (currentBudget?.status !== "CONFIRMED" || currentBudget.month !== mockPeriod(todayKey).month) return [];
  return budgetConfirmedMock(todayKey, currentBudget.amounts).envelopes
    .filter((envelope) => envelope.confirmedAmount !== null && envelope.spent !== null && envelope.spent > envelope.confirmedAmount)
    .map((envelope) => envelope.envelopeId);
}

/** 테스트·개발 재시작용 */
/**
 * PUT /budgets/{budgetId}/emergency 목. 서버처럼 0 이상 1,000원 단위만 받고 다른 예산 id 는 404 다.
 * 0 을 보내면 해제(미설정)이며, 바뀐 값은 GET /budgets/current 의 emergency 로도 그대로 나온다.
 */
export function updateEmergencyFundMock(budgetId: number, request: EmergencyFundRequest): EmergencyFundResponseDto {
  if (budgetId !== MOCK_BUDGET_ID) throw new ApiError(404, "BUDGET_002", "예산을 찾을 수 없습니다.");
  if (!Number.isSafeInteger(request.amount) || request.amount < 0) throw new ApiError(400, "COMMON_001", "금액이 올바르지 않습니다.");
  if (request.amount % 1000 !== 0) throw new ApiError(400, "BUDGET_005", "1,000원 단위로 입력해 주세요.");

  emergencyAmount = request.amount;
  return { budgetId, emergency: emergencyState() };
}

export function resetBudgetMocks(): void {
  emergencyAmount = 0;
  currentBudget = null;
}
