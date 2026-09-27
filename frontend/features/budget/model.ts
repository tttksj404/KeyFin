import { ContractMismatchError } from "@/lib/contract";
import { addKRW, compareKRW, fromServerWon, toWon, type KRW } from "@/lib/money";

/**
 * GET /budgets/current 계약 (노션 "예산·잔액 조회" · 백엔드 develop 코드, 2026-09-12 대조).
 * 서버가 요청 시점과 사용자 기준일로 현재 주기를 정한다. 이번 주기 예산이 없으면 서버가 제안을 만들어 PROPOSED 로 준다.
 * - PROPOSED: total=null, 봉투는 proposedAmount 만(나머지 null)
 * - CONFIRMED: 봉투 proposedAmount=null, 확정액·지출·잔액·잔여율. 확정액 0 인 봉투는 remainingRate=null
 * 잔액·잔여율은 서버 파생값이라 검증만 하고 다시 계산하지 않는다.
 */
export type BudgetStatus = "PROPOSED" | "CONFIRMED" | "UNKNOWN";

export type BudgetEnvelopeDto = {
  envelopeId: number;
  name: string;
  proposedAmount: number | null;
  confirmedAmount: number | null;
  spent: number | null;
  remaining: number | null;
  /** 정수 %, 내림, 초과면 음수. 확정액 0 이면 null */
  remainingRate: number | null;
};

export type BudgetTotalDto = {
  confirmed: number;
  /** 확정액 0 봉투의 지출도 포함한다 */
  spent: number;
  remaining: number;
  remainingRate: number | null;
};

export type BudgetDto = {
  /** 승인 API(PUT /budgets/{budgetId}/confirm) 경로 값 */
  budgetId: number;
  /** 주기 시작일이 속한 달 라벨. 기준일 사용자는 달력 월과 달라 화면에 "N월"로 쓰지 않는다 */
  month: string;
  /** "YYYY-MM-DD" 주기 시작일(= 기준일) */
  periodFrom: string;
  /** "YYYY-MM-DD" 주기 마지막 날(포함) */
  periodTo: string;
  status: string;
  total: BudgetTotalDto | null;
  envelopes: BudgetEnvelopeDto[];
  /** 비상금 가상 풀. PROPOSED·CONFIRMED 모두 항상 온다 (백엔드 a95d9e1, 2026-09-16 대조) */
  emergency: BudgetEmergencyDto;
};

/** amount 0 = 미설정. spent 는 주기 안 EMERGENCY 태그 거래 합이고 remaining 은 음수가 될 수 있다 */
export type BudgetEmergencyDto = { amount: number; spent: number; remaining: number };

export type BudgetEnvelope = {
  envelopeId: number;
  name: string;
  /** PROPOSED 에서만 있다 */
  proposed: KRW | null;
  confirmed: KRW | null;
  spent: KRW | null;
  remaining: KRW | null;
  remainingRate: number | null;
};

export type BudgetTotal = {
  confirmed: KRW;
  spent: KRW;
  remaining: KRW;
  /** 전체 확정액이 0 이면 null */
  remainingRate: number | null;
};

export type BudgetEmergency = {
  /** "0" 이면 미설정이다 */
  amount: KRW;
  spent: KRW;
  /** amount − spent. 넘겨 썼으면 음수 */
  remaining: KRW;
};

export type Budget = {
  budgetId: number;
  month: string;
  periodFrom: string;
  periodTo: string;
  status: BudgetStatus;
  isConfirmed: boolean;
  /** 승인 전이면 null */
  total: BudgetTotal | null;
  envelopes: BudgetEnvelope[];
  /** 비상금 풀(P1 설정 화면 전까지 화면에 쓰는 곳은 없다). amount "0" 이면 미설정 */
  emergency: BudgetEmergency;
};

/** 화면 표시용 상태. over = 남은 예산 음수, warning = 잔여율 30% 미만(잔액 구간 알림 30% 와 같은 기준), good = 나머지 */
export type BudgetHealth = "good" | "warning" | "over";

export const WARNING_REMAINING_RATE = 30;

const MONTH_KEY = /^\d{6}$/;

function won(value: number, field: string): KRW {
  try {
    return fromServerWon(value);
  } catch {
    throw new ContractMismatchError(field);
  }
}

function optionalWon(value: number | null, field: string): KRW | null {
  return value === null ? null : won(value, field);
}

function requiredRate(value: number, field: string): number {
  if (!Number.isInteger(value)) throw new ContractMismatchError(field);
  return value;
}

function optionalRate(value: number | null, field: string): number | null {
  return value === null ? null : requiredRate(value, field);
}

function toStatus(raw: string): BudgetStatus {
  return raw === "PROPOSED" || raw === "CONFIRMED" ? raw : "UNKNOWN";
}

function toTotal(dto: BudgetTotalDto | null): BudgetTotal | null {
  if (dto === null) return null;
  return {
    confirmed: won(dto.confirmed, "total.confirmed"),
    spent: won(dto.spent, "total.spent"),
    remaining: won(dto.remaining, "total.remaining"),
    remainingRate: optionalRate(dto.remainingRate, "total.remainingRate"),
  };
}

const DATE_KEY = /^\d{4}-\d{2}-\d{2}$/;

export function toBudget(dto: BudgetDto): Budget {
  if (!Number.isSafeInteger(dto.budgetId) || dto.budgetId <= 0) throw new ContractMismatchError("budgetId");
  if (!MONTH_KEY.test(dto.month)) throw new ContractMismatchError("month");
  if (!DATE_KEY.test(dto.periodFrom)) throw new ContractMismatchError("periodFrom");
  if (!DATE_KEY.test(dto.periodTo) || dto.periodTo < dto.periodFrom) throw new ContractMismatchError("periodTo");
  const status = toStatus(dto.status);
  const total = toTotal(dto.total);
  if (status === "CONFIRMED" && total === null) throw new ContractMismatchError("total");

  return {
    budgetId: dto.budgetId,
    month: dto.month,
    periodFrom: dto.periodFrom,
    periodTo: dto.periodTo,
    status,
    isConfirmed: status === "CONFIRMED",
    total,
    envelopes: dto.envelopes.map((envelope) => {
      if (status === "PROPOSED" && envelope.proposedAmount === null) throw new ContractMismatchError("envelopes.proposedAmount");
      return {
        envelopeId: envelope.envelopeId,
        name: envelope.name,
        proposed: optionalWon(envelope.proposedAmount, "envelopes.proposedAmount"),
        confirmed: optionalWon(envelope.confirmedAmount, "envelopes.confirmedAmount"),
        spent: optionalWon(envelope.spent, "envelopes.spent"),
        remaining: optionalWon(envelope.remaining, "envelopes.remaining"),
        remainingRate: optionalRate(envelope.remainingRate, "envelopes.remainingRate"),
      };
    }),
    emergency: toEmergency(dto.emergency),
  };
}

/** 응답에 비상금이 없으면(구 서버) 미설정으로 본다 */
function toEmergency(dto: BudgetEmergencyDto | null | undefined): BudgetEmergency {
  if (dto === null || dto === undefined) return { amount: "0", spent: "0", remaining: "0" };
  return {
    amount: won(dto.amount, "emergency.amount"),
    spent: won(dto.spent, "emergency.spent"),
    remaining: won(dto.remaining, "emergency.remaining"),
  };
}

function monthDayOf(dateKey: string): { month: number; day: number } {
  return { month: Number(dateKey.slice(5, 7)), day: Number(dateKey.slice(8, 10)) };
}

/**
 * 주기를 "9월 1일~30일"(같은 달) · "8월 23일~9월 22일"(달이 넘어갈 때)로 쓴다.
 * 주기 라벨(month)은 기준일 사용자에게 달력 월과 달라 "8월"처럼 쓰지 않는다 (노션 예산·잔액 조회).
 */
export function budgetPeriodLabel(budget: Pick<Budget, "periodFrom" | "periodTo">): string {
  const from = monthDayOf(budget.periodFrom);
  const to = monthDayOf(budget.periodTo);
  return from.month === to.month
    ? `${from.month}월 ${from.day}일~${to.day}일`
    : `${from.month}월 ${from.day}일~${to.month}월 ${to.day}일`;
}

/** 좁은 자리(방 벽 보드)용 "9.1~9.30" */
export function budgetPeriodShortLabel(budget: Pick<Budget, "periodFrom" | "periodTo">): string {
  const from = monthDayOf(budget.periodFrom);
  const to = monthDayOf(budget.periodTo);
  return `${from.month}.${from.day}~${to.month}.${to.day}`;
}

/** 거래일("YYYY-MM-DD")이 이 주기 안인지. 분류를 확정했을 때 현재 주기 예산을 다시 받아야 하는지 가른다 */
export function isWithinPeriod(budget: Pick<Budget, "periodFrom" | "periodTo">, dateKey: string): boolean {
  return dateKey >= budget.periodFrom && dateKey <= budget.periodTo;
}

const POSITIVE_ID = /^[1-9]\d*$/;

/** 봉투 상세 라우트(`/budget/[envelopeId]`)의 id. 양의 정수가 아니면 null — 라우트 파라미터는 믿지 않는다 */
export function parseEnvelopeId(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw !== undefined && POSITIVE_ID.test(raw) ? Number(raw) : null;
}

export function budgetHealth(total: BudgetTotal): BudgetHealth {
  if (compareKRW(total.remaining, "0") < 0) return "over";
  if (total.remainingRate !== null && total.remainingRate < WARNING_REMAINING_RATE) return "warning";
  return "good";
}

/** 봉투별 상태. 승인 전(확정액·잔액 null)은 unset */
export type EnvelopeHealth = BudgetHealth | "unset";

/**
 * 확정액 0 인 봉투는 잔여율이 null 이다(노션 제안, 사용자 결정 2026-09-12): 막대는 빈 트랙으로 두고,
 * 지출이 있으면 잔액이 음수라 over(초과 색·금액 텍스트), 지출도 없으면 경고할 게 없어 good 이다.
 */
export function envelopeHealth(envelope: BudgetEnvelope): EnvelopeHealth {
  if (envelope.confirmed === null || envelope.remaining === null) return "unset";
  if (compareKRW(envelope.remaining, "0") < 0) return "over";
  if (envelope.remainingRate === null) return "good";
  if (envelope.remainingRate < WARNING_REMAINING_RATE) return "warning";
  return "good";
}

/** 서버 잔여율(%)을 사용률(%)로 바꾼다. 초과면 100 을 넘는다 — 막대 길이는 호출부가 100 으로 자른다. */
export function usedPercent(remainingRate: number): number {
  return Math.max(0, 100 - remainingRate);
}

/** 막대 길이(0~100). 잔여율이 없으면(확정액 0) 빈 트랙이다 */
export function usedBarPercent(remainingRate: number | null): number {
  return remainingRate === null ? 0 : Math.min(100, usedPercent(remainingRate));
}

/**
 * POST /budgets/proposals 계약 (docs/api-contract.md BUDGET, FR-USR-04·FR-BGT-01).
 * 조회(GET /budgets/{month})와 달리 봉투마다 근거인 monthlyAvg 가 온다 — 승인 화면(PAGE-07)이 이걸 쓴다.
 */
export type BudgetProposalEnvelopeDto = {
  envelopeId: number;
  name: string;
  proposedAmount: number;
  /** 최근 3개월 월평균 소비 */
  monthlyAvg: number;
  adjustment?: number;
};

export type BudgetProposalDto = {
  budgetId: number;
  month: string;
  status: string;
  /** 제안 근거 문구. 이력이 없으면 기본 템플릿 폴백 */
  basis: string;
  envelopes: BudgetProposalEnvelopeDto[];
};

export type BudgetProposalEnvelope = {
  envelopeId: number;
  name: string;
  proposed: KRW;
  monthlyAvg: KRW;
};

export type BudgetProposal = {
  budgetId: number;
  month: string;
  status: BudgetStatus;
  basis: string;
  envelopes: BudgetProposalEnvelope[];
};

export function toBudgetProposal(dto: BudgetProposalDto): BudgetProposal {
  if (!MONTH_KEY.test(dto.month)) throw new ContractMismatchError("month");
  if (!Number.isInteger(dto.budgetId)) throw new ContractMismatchError("budgetId");

  return {
    budgetId: dto.budgetId,
    month: dto.month,
    status: toStatus(dto.status),
    basis: dto.basis,
    envelopes: dto.envelopes.map((envelope) => ({
      envelopeId: envelope.envelopeId,
      name: envelope.name,
      proposed: won(envelope.proposedAmount, "envelopes.proposedAmount"),
      monthlyAvg: won(envelope.monthlyAvg, "envelopes.monthlyAvg"),
    })),
  };
}

/**
 * 지난 소비를 분석한 제안인지. 이력이 없으면 서버가 기본 템플릿 금액으로 채우고 월평균은 전부 0 이다.
 * basis 문구로 가르지 않고 값으로 판단한다. false 면 소비 분석 결과(PAGE-06 A·B)를 건너뛰고 예산 제안으로 간다.
 */
export function hasSpendingHistory(proposal: BudgetProposal): boolean {
  return proposal.envelopes.some((envelope) => compareKRW(envelope.monthlyAvg, "0") > 0);
}

/**
 * 예산 확정 화면의 안내 문구 종류. history = 지난 소비를 분석한 제안, template = 이력이 없어 기본 예산,
 * unknown = 분석 결과가 캐시에 없다(홈에서 강제로 왔거나 앱을 다시 켰다) — 제안액만 있다.
 */
export type ProposalBasisKind = "history" | "template" | "unknown";

export function proposalBasisKind(budget: Budget, analysis: BudgetProposal | undefined): ProposalBasisKind {
  if (analysis === undefined || analysis.budgetId !== budget.budgetId) return "unknown";
  return hasSpendingHistory(analysis) ? "history" : "template";
}

/** 예산 확정 화면(PAGE-07)의 봉투 행. 금액은 현재 주기 예산(PROPOSED)의 제안액, 월평균은 같은 예산의 분석 결과가 있을 때만 */
export type ProposalRow = { envelopeId: number; name: string; proposed: KRW; monthlyAvg: KRW | null };

/**
 * 제안액은 GET /budgets/current 에서, 근거(월평균)는 온보딩 분석(POST /budgets/proposals) 캐시에서 온다.
 * 분석 캐시가 다른 예산 것이면(budgetId 가 다르면) 섞지 않는다.
 */
export function toProposalRows(budget: Budget, analysis: BudgetProposal | undefined): ProposalRow[] {
  const sameBudget = analysis !== undefined && analysis.budgetId === budget.budgetId ? analysis : undefined;
  return budget.envelopes.map((envelope) => ({
    envelopeId: envelope.envelopeId,
    name: envelope.name,
    proposed: envelope.proposed ?? "0",
    monthlyAvg: sameBudget?.envelopes.find((row) => row.envelopeId === envelope.envelopeId)?.monthlyAvg ?? null,
  }));
}

/** 월평균이 큰 순. 같으면 원래 봉투 순서를 지킨다(정렬이 안정적이다) */
export function sortByMonthlyAvg(envelopes: readonly BudgetProposalEnvelope[]): BudgetProposalEnvelope[] {
  return [...envelopes].sort((a, b) => compareKRW(b.monthlyAvg, a.monthlyAvg));
}

/** 막대 길이(0~100 정수). 가장 많이 쓴 봉투를 100 으로 본다 */
export function monthlyAvgPercent(value: KRW, max: KRW): number {
  const maxWon = toWon(max);
  if (maxWon <= 0n) return 0;
  return Number((toWon(value) * 100n) / maxWon);
}

/** PUT /budgets/{budgetId}/confirm 요청. 봉투 7개를 전부 보낸다(구성이 다르면 400 BUDGET_004) */
export type ConfirmBudgetRequest = {
  envelopes: { envelopeId: number; amount: number }[];
};

export type ConfirmBudgetResponseDto = { budgetId: number; month: string; status: string };

/** 화면의 KRW 문자열 금액을 서버가 받는 원 정수로 되돌린다 */
export function toConfirmRequest(entries: { envelopeId: number; amount: KRW }[]): ConfirmBudgetRequest {
  return {
    envelopes: entries.map(({ envelopeId, amount }) => ({ envelopeId, amount: Number(toWon(amount)) })),
  };
}

/** 봉투 금액 합계. 빈 목록은 0 원이다 */
export function sumAmounts(amounts: KRW[]): KRW {
  return amounts.length === 0 ? "0" : addKRW(...amounts);
}

/* ───────────── 비상금: PUT /budgets/{budgetId}/emergency (배포 서버 Swagger 2026-09-20 대조, FR-BGT-09) ───────────── */

/**
 * 비상금은 실제 계좌가 아니라 가상 풀이다. 사용액은 주기 안 EMERGENCY 태그 거래의 합이고 잔액은 설정액 − 사용액이라 음수가 될 수 있다.
 * 금액은 0 이상 1,000원 단위이며 0 이면 해제(미설정과 같다). 예산 확정 여부와 무관하게 주기 중 언제든 바꿀 수 있고
 * 이체·예산 제안·봉투 잔액에는 영향을 주지 않는다. 같은 값이 GET /budgets/current 의 emergency 로도 온다.
 */
export const EMERGENCY_AMOUNT_UNIT = 1000n;

export type EmergencyFundRequest = { amount: number };

export type EmergencyFundResponseDto = { budgetId: number; emergency: BudgetEmergencyDto };

export type EmergencyFund = { budgetId: number; emergency: BudgetEmergency };

export function toEmergencyFund(dto: EmergencyFundResponseDto): EmergencyFund {
  if (!Number.isSafeInteger(dto.budgetId) || dto.budgetId <= 0) throw new ContractMismatchError("budgetId");
  return { budgetId: dto.budgetId, emergency: toEmergency(dto.emergency) };
}

/** 입력 칸은 빈 값을 미설정(0)으로 본다 */
function emergencyWon(digits: string): bigint {
  return digits === "" ? 0n : toWon(digits);
}

/** 저장할 수 없는 이유. 없으면 null. 서버도 같은 기준으로 막는다(400 COMMON_001 · BUDGET_005) */
export function emergencyAmountError(digits: string): string | null {
  const amount = emergencyWon(digits);
  if (amount < 0n) return "0원 이상으로 정해 주세요.";
  if (amount % EMERGENCY_AMOUNT_UNIT !== 0n) return "1,000원 단위로 정해 주세요.";
  return null;
}

export function toEmergencyFundRequest(digits: string): EmergencyFundRequest {
  const error = emergencyAmountError(digits);
  if (error !== null) throw new Error(error);
  return { amount: Number(emergencyWon(digits)) };
}

/** 지금 설정액과 같으면 저장 버튼을 켜지 않는다. 미설정("0")은 빈 칸과 같은 값으로 본다 */
export function isEmergencyDirty(digits: string, emergency: BudgetEmergency): boolean {
  return emergencyWon(digits) !== toWon(emergency.amount);
}

/** 설정 칸의 처음 값. 미설정이면 빈 칸으로 둔다 */
export function toEmergencyInput(emergency: BudgetEmergency): string {
  return toWon(emergency.amount) === 0n ? "" : emergency.amount;
}
