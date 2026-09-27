import { isApiError } from "@/api/error";

/**
 * 금융망 연결 오류 문구 (docs/api-contract.md §3-0).
 * 정의가 없는 code 는 서버 message 를 그대로 쓴다 (규칙 90).
 */
const FINANCE_MESSAGES: Record<string, string> = {
  FINANCE_001: "그 이메일로 가입된 금융망 회원이 없어요. 금융망에 가입한 이메일이 맞는지 확인해 주세요.",
  FINANCE_002: "금융망 응답을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.",
  FINANCE_003: "금융망 연동 설정에 문제가 있어요. 잠시 후 다시 시도해 주세요.",
  FINANCE_004: "금융망이 잠시 응답하지 않아요. 잠시 후 다시 시도해 주세요.",
  LINK_001: "그 금융망 계정은 이미 다른 KeyFin 계정과 연결돼 있어요.",
  USER_004: "이미 다른 금융망 계정과 연결돼 있어요.",
  USER_001: "사용자 정보를 찾을 수 없어요. 다시 로그인해 주세요.",
  COMMON_001: "이메일 형식을 다시 확인해 주세요.",
  COMMON_002: "요청을 처리하지 못했어요. 다시 시도해 주세요.",
};

const UNKNOWN_MESSAGE = "금융망에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.";

/** 다시 눌러도 결과가 같은 오류. 재시도 안내를 붙이지 않는다 */
const NOT_RETRYABLE = ["LINK_001", "USER_004", "FINANCE_001"];

export function financeErrorMessage(error: unknown): string {
  if (!isApiError(error)) return UNKNOWN_MESSAGE;
  return FINANCE_MESSAGES[error.code] ?? (error.message !== "" ? error.message : UNKNOWN_MESSAGE);
}

export function isRetryableFinanceError(error: unknown): boolean {
  return isApiError(error) ? !NOT_RETRYABLE.includes(error.code) : true;
}

/**
 * POST /links 실패 문구 (docs/api-contract.md LINK). 금융망을 부르지 않는 API 라 FINANCE_* 는 오지 않는다.
 * 금융망 회원 연결과 code 가 겹쳐도 원인이 달라(COMMON_001 은 이메일이 아니라 id 목록 오류) 표를 따로 둔다.
 */
const LINK_MESSAGES: Record<string, string> = {
  COMMON_001: "계좌와 카드는 한 번에 50개까지 연결할 수 있어요.",
  LINK_003: "연결할 계좌나 카드를 골라 주세요.",
  LINK_004: "선택한 계좌를 찾을 수 없어요. 목록을 새로 불러왔으니 다시 골라 주세요.",
  LINK_005: "선택한 카드를 찾을 수 없어요. 목록을 새로 불러왔으니 다시 골라 주세요.",
};

/** 고른 id 가 후보에서 사라진 오류(LINK_004·LINK_005). 서버 안내대로 후보 목록을 다시 받는다 */
const STALE_CANDIDATE_CODES = ["LINK_004", "LINK_005"];

export function isStaleCandidateError(error: unknown): boolean {
  return isApiError(error) && STALE_CANDIDATE_CODES.includes(error.code);
}

const LINK_UNKNOWN_MESSAGE = "자산을 연결하지 못했어요. 잠시 후 다시 시도해 주세요.";

/** 금융망 회원 미연결(LINK_002)·userKey 무효(FINANCE_005). 다시 시도로는 풀리지 않아 금융망 이메일 연결로 보낸다 */
const FINANCE_RECONNECT_CODES = ["LINK_002", "FINANCE_005"];

export function needsFinanceReconnect(error: unknown): boolean {
  return isApiError(error) && FINANCE_RECONNECT_CODES.includes(error.code);
}

export function linkErrorMessage(error: unknown): string {
  if (!isApiError(error)) return LINK_UNKNOWN_MESSAGE;
  return LINK_MESSAGES[error.code] ?? (error.message !== "" ? error.message : LINK_UNKNOWN_MESSAGE);
}

/**
 * 연결 해제(DELETE /links/accounts|cards/{id}) 실패 문구 (docs/api-contract.md LINK, 2026-09-17 코드 대조).
 * 이미 해제된 항목은 200 이라 404 는 목록에서 사라진(본인 소유가 아닌) 항목이다 — 선택 화면 문구와 달리 다시 고르라고 하지 않는다.
 */
const UNLINK_MESSAGES: Record<string, string> = {
  LINK_004: "이미 목록에서 사라진 계좌예요. 목록을 새로 불러왔어요.",
  LINK_005: "이미 목록에서 사라진 카드예요. 목록을 새로 불러왔어요.",
  USER_001: "사용자 정보를 찾을 수 없어요. 다시 로그인해 주세요.",
};

const UNLINK_UNKNOWN_MESSAGE = "연결을 해제하지 못했어요. 잠시 후 다시 시도해 주세요.";

export function unlinkErrorMessage(error: unknown): string {
  if (!isApiError(error)) return UNLINK_UNKNOWN_MESSAGE;
  return UNLINK_MESSAGES[error.code] ?? (error.message !== "" ? error.message : UNLINK_UNKNOWN_MESSAGE);
}
