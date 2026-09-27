import { Pressable, View } from "react-native";

import { getSceneScale, type SceneRect } from "@/features/room/model";

// Pencil home/p0 Calendar Asset (lrclI). 그림(나무 레일 + 달력 종이)은 Skia 씬이 스프라이트(WALL_ITEMS.calendar)로 그리고,
// 이 컴포넌트는 그 위에 얹는 탭 영역과 준비 부족 점(Calendar ShortageDot, Fycy2)뿐이다 — 벽걸이가 1×1 칸이라 글자를 얹지 않고
// 월·날짜·이름은 팝오버(CalendarPopover)가 보여준다(사용자 결정 2026-09-15). 자리는 배치(스토어)에서 온 사각형이다.
const SHORTAGE_DOT_SIZE = 12;
export const CALENDAR_EMPTY_LABEL = "예정 없음";

/** 방 컴포넌트는 결제 도메인 타입에 의존하지 않는다 — 다음 출금 한 건만 받는다 */
export type UpcomingPayment = {
  /** 날짜의 일(1~31) */
  day: number;
  name: string;
  hasShortage: boolean;
};

type CalendarAssetProps = {
  /** 캔버스 폭(pt). 씬 좌표를 이 폭으로 환산한다 */
  width: number;
  /** 캘린더 스프라이트가 놓인 씬 사각형 */
  rect: SceneRect;
  /** "9월" */
  monthLabel: string;
  /** 이번 달 출금 예정이 없으면 null */
  upcoming: UpcomingPayment | null;
  onPress: () => void;
};

function CalendarAsset({ width, rect, monthLabel, upcoming, onPress }: CalendarAssetProps) {
  const scale = getSceneScale(width);
  const status = upcoming
    ? `${upcoming.day}일 ${upcoming.name}${upcoming.hasShortage ? ", 준비 부족" : ""}`
    : `출금 ${CALENDAR_EMPTY_LABEL}`;
  const dot = SHORTAGE_DOT_SIZE * scale;

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`출금 캘린더, ${monthLabel} ${status}`}
        accessibilityHint="이번 달 출금 일정을 엽니다"
        onPress={onPress}
        hitSlop={8}
        className="absolute active:opacity-80"
        style={{ left: rect.x * scale, top: rect.y * scale, width: rect.width * scale, height: rect.height * scale }}
      />
      {upcoming?.hasShortage ? (
        <View
          accessible={false}
          className="absolute rounded-full bg-destructive"
          style={{ left: (rect.x + rect.width) * scale - dot * 0.6, top: rect.y * scale - dot * 0.4, width: dot, height: dot }}
        />
      ) : null}
    </>
  );
}

export { CalendarAsset };
export type { CalendarAssetProps };
