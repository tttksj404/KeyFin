import { isApiError } from "@/api/error";

const UNKNOWN_MESSAGE = "설정을 저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/**
 * 이체 설정 저장(PUT /settings/transfer) 실패 문구.
 * USER_005(한도 0 이하·1회 > 1일)는 화면 검사가 먼저 막으므로 넘어온 오류는 서버 message 를 쓰고 없으면 기본 문구다 (규칙 90).
 */
export function transferSettingsErrorMessage(error: unknown): string {
  if (!isApiError(error) || error.message === "") return UNKNOWN_MESSAGE;
  return error.message;
}

const NOTIFICATION_UNKNOWN_MESSAGE = "알림 설정을 저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/** 알림 설정 저장(PUT /settings/notifications) 실패 문구 (배포 서버 Swagger 2026-09-20) */
const NOTIFICATION_MESSAGES: Record<string, string> = {
  USER_009: "방해 금지 시간을 다시 골라 주세요.",
  USER_006: "설정을 찾을 수 없어요. 다시 로그인해 주세요.",
  COMMON_001: "입력한 내용을 다시 확인해 주세요.",
};

export function notificationSettingsErrorMessage(error: unknown): string {
  if (!isApiError(error)) return NOTIFICATION_UNKNOWN_MESSAGE;
  return NOTIFICATION_MESSAGES[error.code] ?? (error.message !== "" ? error.message : NOTIFICATION_UNKNOWN_MESSAGE);
}

const COACH_UNKNOWN_MESSAGE = "코치 말투를 바꾸지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/** 코치 말투 변경(PUT /settings/coach) 실패 문구 */
const COACH_MESSAGES: Record<string, string> = {
  COMMON_002: "지금은 고를 수 없는 말투예요.",
  USER_006: "설정을 찾을 수 없어요. 다시 로그인해 주세요.",
};

export function coachPersonaErrorMessage(error: unknown): string {
  if (!isApiError(error)) return COACH_UNKNOWN_MESSAGE;
  return COACH_MESSAGES[error.code] ?? (error.message !== "" ? error.message : COACH_UNKNOWN_MESSAGE);
}
