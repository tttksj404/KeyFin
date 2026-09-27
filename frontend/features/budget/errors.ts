import { isApiError } from "@/api/error";

const PROPOSAL_UNKNOWN_MESSAGE = "잠시 후 다시 시도해 주세요.";

/** 예산 제안(POST /budgets/proposals) 실패 문구. 따로 정한 code 가 없어 서버 message 를 쓴다 (규칙 90) */
export function proposalErrorMessage(error: unknown): string {
  if (!isApiError(error) || error.message === "") return PROPOSAL_UNKNOWN_MESSAGE;
  return error.message;
}

/**
 * 예산 승인(PUT /budgets/{budgetId}/confirm) 실패 문구 (노션 "예산 승인·조정", 2026-09-12 대조).
 * 확정은 주기당 1회라 BUDGET_003 은 다시 눌러도 같다. 004·005·COMMON_001 은 앱이 보낸 값이 틀린 경우다.
 */
const CONFIRM_MESSAGES: Record<string, string> = {
  BUDGET_002: "예산 제안을 찾을 수 없어요. 처음부터 다시 시도해 주세요.",
  BUDGET_003: "이번 달 예산은 이미 확정됐어요. 확정한 뒤에는 바꿀 수 없어요.",
  BUDGET_004: "봉투 구성이 맞지 않아 저장하지 못했어요. 화면을 다시 열어 주세요.",
  BUDGET_005: "예산 금액은 1,000원 단위로 정해 주세요.",
  COMMON_001: "입력한 금액을 다시 확인해 주세요.",
};

const CONFIRM_UNKNOWN_MESSAGE = "예산을 저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.";

export function confirmErrorMessage(error: unknown): string {
  if (!isApiError(error)) return CONFIRM_UNKNOWN_MESSAGE;
  return CONFIRM_MESSAGES[error.code] ?? (error.message !== "" ? error.message : CONFIRM_UNKNOWN_MESSAGE);
}

/** 이미 확정된 예산(BUDGET_003). 확정은 주기당 1회라 서버에선 끝난 상태다 — 다음 단계로 넘긴다(사용자 결정 2026-09-12) */
export function isAlreadyConfirmedError(error: unknown): boolean {
  return isApiError(error) && error.code === "BUDGET_003";
}

/** 이번 주기 예산이 이미 있음(BUDGET_001). 제안을 다시 만들 수 없으니 GET /budgets/current 로 받는다 */
export function isBudgetExistsError(error: unknown): boolean {
  return isApiError(error) && error.code === "BUDGET_001";
}

const EMERGENCY_UNKNOWN_MESSAGE = "비상금을 저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/** 비상금 설정(PUT /budgets/{budgetId}/emergency) 실패 문구 (배포 서버 Swagger 2026-09-20) */
const EMERGENCY_MESSAGES: Record<string, string> = {
  BUDGET_002: "예산을 찾을 수 없어요. 화면을 새로 불러온 뒤 다시 시도해 주세요.",
  BUDGET_005: "비상금은 1,000원 단위로 정해 주세요.",
  COMMON_001: "입력한 금액을 다시 확인해 주세요.",
};

export function emergencyFundErrorMessage(error: unknown): string {
  if (!isApiError(error)) return EMERGENCY_UNKNOWN_MESSAGE;
  return EMERGENCY_MESSAGES[error.code] ?? (error.message !== "" ? error.message : EMERGENCY_UNKNOWN_MESSAGE);
}
