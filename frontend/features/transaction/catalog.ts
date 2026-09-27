import type { UserExcludeTag } from "@/features/transaction/model";

/**
 * 세분류 시트의 "예산에서 제외" 선택지 (FR-TXN-05). 라벨은 기획 문구.
 * 비상금(EMERGENCY)은 노션 명세대로 비상금 기능 연동 전까지 쓸 수 없어 뺐다(2026-09-15).
 */
export const USER_EXCLUDE_TAGS: { tag: UserExcludeTag; label: string; description: string }[] = [
  { tag: "DUTCH", label: "더치페이", description: "내 몫만 낸 결제" },
  { tag: "SELF_TRANSFER", label: "내 계좌 이동", description: "내 계좌끼리 옮긴 돈" },
];
