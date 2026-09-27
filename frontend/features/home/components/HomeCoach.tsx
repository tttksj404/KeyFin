import { useRouter } from "expo-router";

import { CoachTarget } from "@/features/home/components/CoachTarget";
import type { CoachSpeechView } from "@/features/home/useCoachSpeech";
import type { SceneSize } from "@/features/room/model";

/** 코치 고양이를 누르면 여는 코칭 대화 화면 (PAGE-31) */
export const COACHING_CHAT_ROUTE = "/coaching/chat";

type HomeCoachTargetProps = {
  /** 캔버스 폭(pt) */
  width: number;
  /** 실제 홈 표시 영역. 방 캔버스가 화면보다 넓거나 높을 수 있다. */
  viewport?: SceneSize;
  /** 눌러서 이동하기 직전에 부른다(첫 진입 안내를 끝내는 데 쓴다) */
  onOpen?: () => void;
  /** 머리 위 말풍선·대화 아이콘 상태. 없으면 null */
  speech?: CoachSpeechView | null;
};

/**
 * 방의 코치(고양이) 탭 영역. 누르면 코칭 대화 화면으로 간다(2026-09-22 사용자 요청 — 2026-09-15 의 임시 "?" 말풍선을 대신한다).
 * 말풍선 아이콘은 안내만 펼치고, 고양이를 눌렀을 때만 화면을 이동한다. 정리 링크는 대화 화면 상단에 있다.
 */
function HomeCoachTarget({ width, viewport, onOpen, speech = null }: HomeCoachTargetProps) {
  const router = useRouter();
  const open = () => {
    onOpen?.();
    router.push(COACHING_CHAT_ROUTE);
  };
  return (
    <CoachTarget
      width={width}
      viewport={viewport}
      speech={speech}
      onPress={open}
    />
  );
}

export { HomeCoachTarget };
export type { HomeCoachTargetProps };
