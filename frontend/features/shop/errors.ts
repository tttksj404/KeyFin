import { isApiError } from "@/api/error";

const PURCHASE_UNKNOWN_MESSAGE = "구매하지 못했어요. 잠시 뒤 다시 시도해 주세요.";

/**
 * 상점 구매 실패 문구 (배포 서버 Swagger POST /shop/purchase, FR-GAM-05).
 * 계약에 있는 code 는 화면 문구로 바꾸고, 정의가 없는 code 는 서버 message 를 쓴다 (규칙 90).
 */
const PURCHASE_MESSAGES: Record<string, string> = {
  SHOP_001: "지금은 팔지 않는 상품이에요. 목록을 새로 불러왔어요.",
  SHOP_002: "이미 가지고 있는 상품이에요. 코인은 빠져나가지 않았어요.",
  SHOP_003: "코인이 모자라요. 출석하거나 거래를 정리하면 코인을 모을 수 있어요.",
  COMMON_001: "상품 정보를 다시 확인해 주세요.",
  COMMON_002: "상품 정보를 다시 확인해 주세요.",
  USER_001: "로그인 정보를 확인할 수 없어요. 다시 로그인해 주세요.",
};

export function shopPurchaseErrorMessage(error: unknown): string {
  if (!isApiError(error)) return PURCHASE_UNKNOWN_MESSAGE;
  return PURCHASE_MESSAGES[error.code] ?? (error.message !== "" ? error.message : PURCHASE_UNKNOWN_MESSAGE);
}

/** 이미 보유라 다시 눌러도 소용없는 실패. 구매 버튼 대신 목록을 새로 받아야 한다 */
export function isAlreadyOwnedError(error: unknown): boolean {
  return isApiError(error) && error.code === "SHOP_002";
}
