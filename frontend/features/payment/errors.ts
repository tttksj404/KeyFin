import { NETWORK_ERROR_CODE, TIMEOUT_ERROR_CODE, isApiError } from "@/api/error";

const SAVE_UNKNOWN_MESSAGE = "고정지출을 저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.";
const DELETE_UNKNOWN_MESSAGE = "고정지출을 삭제하지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/**
 * 고정지출 등록·수정·삭제 실패 문구 (docs/api-contract.md PAYMENT, FR-PAY-07).
 * 계약에 있는 code 는 화면 문구로 바꾸고, 정의가 없는 code 는 서버 message 를 쓴다 (규칙 90).
 */
const FIXED_EXPENSE_MESSAGES: Record<string, string> = {
  PAY_001: "이미 삭제됐거나 찾을 수 없는 고정지출이에요.",
  PAY_002: "카드사에서 관리하는 정기결제라 여기서는 바꿀 수 없어요. 카드사·서비스에서 바꾸면 다음에 반영돼요.",
  PAY_003: "같은 내용의 고정지출이 이미 등록돼 있어요.",
  PAY_004: "카드 대금은 청구서로 계산돼서 직접 등록할 수 없어요.",
  ACCOUNT_001: "출금 계좌를 찾을 수 없어요. 목록을 새로 불러왔으니 다시 골라 주세요.",
  ACCOUNT_002: "연결을 해제한 계좌는 출금 계좌로 쓸 수 없어요. 다른 계좌를 골라 주세요.",
  COMMON_001: "입력한 내용을 다시 확인해 주세요.",
};

function messageOf(error: unknown, fallback: string): string {
  if (!isApiError(error)) return fallback;
  return FIXED_EXPENSE_MESSAGES[error.code] ?? (error.message !== "" ? error.message : fallback);
}

export function fixedExpenseSaveErrorMessage(error: unknown): string {
  return messageOf(error, SAVE_UNKNOWN_MESSAGE);
}

export function fixedExpenseDeleteErrorMessage(error: unknown): string {
  return messageOf(error, DELETE_UNKNOWN_MESSAGE);
}

const CARD_ASSIGN_UNKNOWN_MESSAGE = "결제 카드를 지정하지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/** 정기결제 결제 카드 지정 실패 문구 (백엔드 PaymentErrorCode, -183) */
const CARD_ASSIGN_MESSAGES: Record<string, string> = {
  PAY_001: "이미 해지됐거나 찾을 수 없는 정기결제예요.",
  PAY_013: "카드를 찾을 수 없어요. 목록을 새로 불러왔으니 다시 골라 주세요.",
  PAY_014: "카드 정기결제만 결제 카드를 지정할 수 있어요.",
  PAY_015: "연결을 해제한 카드는 지정할 수 없어요. 다른 카드를 골라 주세요.",
};

export function fixedExpenseCardErrorMessage(error: unknown): string {
  if (!isApiError(error)) return CARD_ASSIGN_UNKNOWN_MESSAGE;
  return CARD_ASSIGN_MESSAGES[error.code] ?? (error.message !== "" ? error.message : CARD_ASSIGN_UNKNOWN_MESSAGE);
}

/** 카드 목록이 서버와 어긋난 오류(카드 없음·미관리). 카드 목록을 다시 받아야 풀린다 */
export function isStaleCardError(error: unknown): boolean {
  return isApiError(error) && (error.code === "PAY_013" || error.code === "PAY_015");
}

/** 화면이 들고 있던 고정지출이 서버와 어긋난 오류(이미 삭제됨·동기화 항목). 목록·캘린더를 다시 받아야 풀린다 */
const STALE_FIXED_EXPENSE_CODES = ["PAY_001", "PAY_002"];

export function isStaleFixedExpenseError(error: unknown): boolean {
  return isApiError(error) && STALE_FIXED_EXPENSE_CODES.includes(error.code);
}

/** 카드 청구 상세의 404. 본인 카드가 아니거나 없는 카드 id 다(딥링크·오래된 화면). 다시 시도해도 풀리지 않는다 */
export function isCardNotFoundError(error: unknown): boolean {
  return isApiError(error) && error.code === "PAY_013";
}

const TRANSFER_UNKNOWN_MESSAGE = "이체를 실행하지 못했어요. 상태를 다시 확인해 주세요.";
const TRANSFER_UNCONFIRMED_MESSAGE = "연결이 끊겨 이체가 됐는지 확인하지 못했어요. 상태를 새로 고쳐 결과를 확인해 주세요.";
const POSTPONE_UNKNOWN_MESSAGE = "나중에로 미루지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/**
 * 이체 승인·연기 실패 문구 (백엔드 PaymentErrorCode, 2026-09-16 대조).
 * 403 넷(PAY_007~010)은 안전장치 4검사라 이체가 아예 실행되지 않았고, 422 둘(PAY_011·012)은 금융망이 거부해 FAILED 로 남는다.
 */
const TRANSFER_MESSAGES: Record<string, string> = {
  PAY_005: "이미 정리됐거나 찾을 수 없는 이체 제안이에요.",
  PAY_006: "지금은 승인할 수 없는 상태예요. 목록을 새로 불러왔어요.",
  PAY_007: "자동 이체 동의가 꺼져 있어요. 설정에서 동의한 뒤 다시 시도해 주세요.",
  PAY_008: "1회 이체 한도를 넘는 금액이에요. 설정에서 한도를 확인해 주세요.",
  PAY_009: "오늘 이체 한도를 다 썼어요. 설정에서 한도를 바꾸거나 내일 다시 시도해 주세요.",
  PAY_010: "출금 계좌가 수입 계좌·관리 대상이 아니에요. 수입 계좌를 다시 지정해 주세요.",
  PAY_011: "출금 계좌 잔액이 부족해 이체하지 못했어요. 계좌를 확인한 뒤 결제일 전에 채워 주세요.",
  PAY_012: "은행 이체 한도를 넘어 이체하지 못했어요. 은행 앱에서 한도를 확인해 주세요.",
  FINANCE_004: "금융망이 잠시 불안정해요. 잠시 뒤 [다시 시도] 를 눌러 주세요.",
};

/** 이체 설정(동의·한도)을 고쳐야 풀리는 오류(안전장치 ①~③). 화면이 이체 설정으로 보낸다 */
const TRANSFER_SETTINGS_CODES = ["PAY_007", "PAY_008", "PAY_009"];

/** 안전장치 ④ — 출금 계좌가 수입·관리 대상이 아님. 이체 설정이 아니라 수입 계좌 지정에서 고친다 */
export function isIncomeAccountError(error: unknown): boolean {
  return isApiError(error) && error.code === "PAY_010";
}

/** 화면이 들고 있던 제안이 서버와 어긋난 오류. 목록을 다시 받아야 풀린다 */
const STALE_TRANSFER_CODES = ["PAY_005", "PAY_006"];

/**
 * 네트워크·타임아웃은 이체가 됐는지 모르는 상태다. 다시 보내지 않고 서버 상태 조회로 확정한다 (규칙 80).
 */
export function isUnconfirmedTransferError(error: unknown): boolean {
  return isApiError(error) && (error.code === NETWORK_ERROR_CODE || error.code === TIMEOUT_ERROR_CODE);
}

export function isTransferSettingsError(error: unknown): boolean {
  return isApiError(error) && TRANSFER_SETTINGS_CODES.includes(error.code);
}

export function isStaleTransferError(error: unknown): boolean {
  return isApiError(error) && STALE_TRANSFER_CODES.includes(error.code);
}

/**
 * 금융망이 잠시 죽은 경우(503 FINANCE_004)는 제안이 APPROVED 로 남고 **다시 승인하면 같은 번호로 재시도**한다.
 * 잔액 부족·은행 한도(422)는 FAILED 로 끝나 재시도 대상이 아니다.
 */
export function isRetryableTransferError(error: unknown): boolean {
  return isApiError(error) && error.code === "FINANCE_004";
}

export function transferApproveErrorMessage(error: unknown): string {
  if (isUnconfirmedTransferError(error)) return TRANSFER_UNCONFIRMED_MESSAGE;
  if (!isApiError(error)) return TRANSFER_UNKNOWN_MESSAGE;
  return TRANSFER_MESSAGES[error.code] ?? (error.message !== "" ? error.message : TRANSFER_UNKNOWN_MESSAGE);
}

export function transferPostponeErrorMessage(error: unknown): string {
  if (!isApiError(error)) return POSTPONE_UNKNOWN_MESSAGE;
  return TRANSFER_MESSAGES[error.code] ?? (error.message !== "" ? error.message : POSTPONE_UNKNOWN_MESSAGE);
}
