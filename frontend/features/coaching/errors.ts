import { isApiError } from "@/api/error";

/**
 * 코칭 오류 코드 (백엔드 develop CoachingErrorCode, 2026-09-23 대조).
 * AI_001 503 코칭 서버 응답 없음 · AI_002 404 차트 없음(다른 계정 포함) · AI_003 422 코칭 서버가 질문을 거절(되묻기 대상이 아닌 4xx).
 */
export const COACH_UNAVAILABLE_CODE = "AI_001";
export const CHART_NOT_FOUND_CODE = "AI_002";
export const COACH_REJECTED_CODE = "AI_003";
export const CHAT_ERROR_MESSAGE = "답변을 받지 못했어요. 다시 시도해 주세요.";

/**
 * 코치 질문(POST /coaching/chat)·이력(GET) 실패 문구. 서버 message 와 같게 둔다.
 * 정의가 없는 code 는 서버 message 를 쓴다 (규칙 90).
 */
const CHAT_MESSAGES: Record<string, string> = {
  [COACH_UNAVAILABLE_CODE]: "코치가 잠시 자리를 비웠어요. 잠시 후 다시 시도해 주세요.",
  [COACH_REJECTED_CODE]: "질문을 이해하지 못했어요. 조금 다르게 물어봐 주세요.",
  [CHART_NOT_FOUND_CODE]: "차트를 찾을 수 없어요.",
  COMMON_001: "질문은 1자 이상 2000자 이하로 적어 주세요.",
};

export function chatErrorMessage(error: unknown): string {
  if (!isApiError(error)) return CHAT_ERROR_MESSAGE;
  return CHAT_MESSAGES[error.code] ?? (error.message !== "" ? error.message : CHAT_ERROR_MESSAGE);
}

/** 코칭 서버가 자리를 비운 것이라 잠시 뒤 다시 시도할 수 있는 실패인지 */
export function isCoachUnavailable(error: unknown): boolean {
  return isApiError(error) && error.code === COACH_UNAVAILABLE_CODE;
}

/** 코칭 서버가 그 질문을 거절한 것(422 AI_003). 같은 질문을 다시 보내도 같아서 다시 시도 대신 다르게 묻게 안내한다 */
export function isCoachRejected(error: unknown): boolean {
  return isApiError(error) && error.code === COACH_REJECTED_CODE;
}

export const CHART_ERROR_MESSAGE = "차트를 불러오지 못했어요. 다시 시도해 주세요.";

/** 차트 HTML(GET /coaching/charts/{chartId}/html) 실패 문구. 코칭 서버 부재(AI_001)는 대화와 같은 문구다 */
export function chartErrorMessage(error: unknown): string {
  if (!isApiError(error)) return CHART_ERROR_MESSAGE;
  return CHAT_MESSAGES[error.code] ?? (error.message !== "" ? error.message : CHART_ERROR_MESSAGE);
}

/** 없거나 다른 계정의 차트(404 AI_002, 2026-09-23 백엔드 확정). 다시 시도해도 같아서 재시도하지 않는다 */
export function isChartNotFoundError(error: unknown): boolean {
  return isApiError(error) && error.code === CHART_NOT_FOUND_CODE;
}
