import { isApiError } from "@/api/error";

const EQUIPMENT_UNKNOWN_MESSAGE = "갈아입지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/**
 * 아바타 장착·해제 실패 문구 (배포 서버 Swagger PATCH /items/{userItemId}, FR-GAM-05).
 * 계약에 있는 code 는 화면 문구로 바꾸고, 정의가 없는 code 는 서버 message 를 쓴다 (규칙 90).
 */
const EQUIPMENT_MESSAGES: Record<string, string> = {
  ITEM_001: "가지고 있지 않은 아이템이에요. 목록을 새로 불러와 주세요.",
  COMMON_001: "아이템 정보를 다시 확인해 주세요.",
  USER_001: "로그인 정보를 확인할 수 없어요. 다시 로그인해 주세요.",
};

export function itemEquipmentErrorMessage(error: unknown): string {
  if (!isApiError(error)) return EQUIPMENT_UNKNOWN_MESSAGE;
  return EQUIPMENT_MESSAGES[error.code] ?? (error.message !== "" ? error.message : EQUIPMENT_UNKNOWN_MESSAGE);
}
