import { NETWORK_ERROR_CODE, TIMEOUT_ERROR_CODE, isApiError } from "@/api/error";

/** 다시 보내면 풀릴 수 있는 기기 등록 오류: 동시 변경(409 PUSH_001, 서버가 3회 재시도 후)과 연결 끊김. 400·404 는 다시 보내도 같다 */
const RETRYABLE_PUSH_CODES = ["PUSH_001", NETWORK_ERROR_CODE, TIMEOUT_ERROR_CODE];

export function isRetryablePushError(error: unknown): boolean {
  return isApiError(error) && RETRYABLE_PUSH_CODES.includes(error.code);
}
