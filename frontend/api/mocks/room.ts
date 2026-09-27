import type { AttendanceDto, RoomDto } from "@/features/room/model";

/**
 * GET /room 응답 예시 (2026-09-16 Swagger 대조 모양). 코인 1,250 · 오늘 출석 전.
 * 슬롯은 서버 ItemSlotType 이다. 가입 시 받는 기본 헤어·표정(FR-USR-01)에 입고 있는 의상 세트가 더해진 모양이며,
 * 세트는 UPPER_BODY 로 온다 — 앱은 assetKey 로 세트를 찾고 못 찾는 값(hair_default 등)은 건너뛴다.
 * 예산 요약(board)은 이 응답에서 빠졌고 벽 보드는 GET /budgets/current 를 쓴다.
 * furnitures 는 설치된 가구 좌표인데 방 배치가 아직 Zustand 에만 있어 빈 배열로 둔다 (3단계).
 */
export const roomMock: RoomDto = {
  avatar: {
    equipped: [
      { userItemId: 11, slotType: "HEAD", itemId: 101, assetKey: "hair_default" },
      { userItemId: 13, slotType: "FACE", itemId: 103, assetKey: "face_default" },
      { userItemId: 501, slotType: "UPPER_BODY", itemId: 1, assetKey: "outfit_epic_mage" },
    ],
    reaction: null,
  },
  furnitures: [],
  coin: { balance: 1250 },
  attendance: { checkedToday: false },
};

/** POST /fin-coins/attendance 응답 예시: 출석 +10 → 잔액 1,260 */
export const attendanceMock: AttendanceDto = { granted: 10, balance: 1260 };
