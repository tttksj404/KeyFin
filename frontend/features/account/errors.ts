import { isApiError } from "@/api/error";

/** PUT /accounts/{id}/income 실패 문구 (docs/api-contract.md ACCOUNT). 정의가 없는 code 는 서버 message 를 쓴다 (규칙 90) */
const INCOME_MESSAGES: Record<string, string> = {
  ACCOUNT_001: "선택한 계좌를 찾을 수 없어요. 목록을 새로 불러왔으니 다시 골라 주세요.",
  ACCOUNT_002: "연결을 해제한 계좌는 수입 계좌로 지정할 수 없어요. 다른 계좌를 골라 주세요.",
};

const INCOME_UNKNOWN_MESSAGE = "수입 계좌를 지정하지 못했어요. 잠시 후 다시 시도해 주세요.";

export function incomeAccountErrorMessage(error: unknown): string {
  if (!isApiError(error)) return INCOME_UNKNOWN_MESSAGE;
  return INCOME_MESSAGES[error.code] ?? (error.message !== "" ? error.message : INCOME_UNKNOWN_MESSAGE);
}

/** 고른 계좌가 목록과 어긋난 오류. 목록을 다시 받아야 풀린다 */
const STALE_ACCOUNT_CODES = ["ACCOUNT_001", "ACCOUNT_002"];

export function isStaleAccountError(error: unknown): boolean {
  return isApiError(error) && STALE_ACCOUNT_CODES.includes(error.code);
}
