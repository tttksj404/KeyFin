import * as React from "react";

import { useAuthStore } from "@/features/auth/store";
import { loadRoomGuideSeen, saveRoomGuideSeen } from "@/lib/session-storage";

/**
 * 홈 첫 진입 안내 (사용자 결정 2026-09-20). 방 안의 리스트·캘린더도, 화면에 떠 있는 버튼도 글자가 없는 그림이라
 * 눌러야 한다는 단서가 없다 — 코치가 한 번만 차례로 짚어 준다.
 * 끝까지 보거나, 그만 보거나, 안내 중에 가리키는 것을 직접 누르면 끝나고 기기에 기록해 다시 보여 주지 않는다.
 */
export type GuideTargetId = "board" | "calendar" | "notification" | "shop" | "wardrobe" | "coach";

export const ROOM_GUIDE_STEPS: readonly { target: GuideTargetId; message: string }[] = [
  { target: "board", message: "벽에 걸린 리스트를 누르면 이번 달 예산과 봉투별 남은 금액을 볼 수 있어요." },
  { target: "calendar", message: "옆의 캘린더는 이번 달 출금 예정일을 알려 줘요." },
  { target: "notification", message: "알림 버튼에서 이체 승인 요청과 예산 알림을 모아 볼 수 있어요." },
  { target: "shop", message: "상점에서는 모은 코인으로 옷과 가구를 살 수 있어요." },
  { target: "wardrobe", message: "옷장을 누르면 가지고 있는 옷으로 캐릭터를 갈아입힐 수 있어요." },
  { target: "coach", message: "저는 코치예요. 궁금한 게 있거나 정리할 결제가 쌓이면 여기를 눌러 주세요." },
];

export type RoomGuideStep = { target: GuideTargetId; message: string; index: number; isLast: boolean };

export type RoomGuide = {
  /** 지금 안내 중인 단계. 안내가 없으면 null */
  step: RoomGuideStep | null;
  next: () => void;
  finish: () => void;
  /** 홈의 "?" 버튼으로 처음부터 다시 본다(사용자 요청 2026-09-23). 끝나면 다시 "봤음"으로 남는다 */
  restart: () => void;
};

/** enabled 는 방이 그려진 뒤에 참이 된다 — 불러오는 중·오류 화면 위에는 안내를 띄우지 않는다 */
export function useRoomGuide(enabled: boolean): RoomGuide {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const [index, setIndex] = React.useState<number | null>(null);
  const finished = React.useRef(false);

  // 기기 저장소(외부 시스템)에서 "봤음" 기록을 읽어 온다
  React.useEffect(() => {
    if (!enabled || userId === null) return;
    let cancelled = false;
    void loadRoomGuideSeen(userId).then((seen) => {
      if (!cancelled && !seen && !finished.current) setIndex(0);
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, userId]);

  const finish = React.useCallback(() => {
    if (finished.current) return;
    finished.current = true;
    setIndex(null);
    if (userId !== null) void saveRoomGuideSeen(userId);
  }, [userId]);

  const restart = React.useCallback(() => {
    finished.current = false;
    setIndex(0);
  }, []);

  const next = React.useCallback(() => {
    if (index === null) return;
    if (index >= ROOM_GUIDE_STEPS.length - 1) finish();
    else setIndex(index + 1);
  }, [index, finish]);

  const current = index === null ? null : ROOM_GUIDE_STEPS[index];
  return {
    step: current && index !== null ? { ...current, index, isLast: index === ROOM_GUIDE_STEPS.length - 1 } : null,
    next,
    finish,
    restart,
  };
}
