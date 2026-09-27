import { useRouter } from "expo-router";

import { usePaymentCalendar } from "@/features/payment/api/queries";
import { CalendarPopover } from "@/features/payment/components/CalendarPopover";
import { upcomingEntry } from "@/features/payment/model";
import { CalendarAsset } from "@/features/room/components/CalendarAsset";
import { getWallItemRect } from "@/features/room/scene";
import { selectPlacements, useRoomStore } from "@/features/room/store";
import { currentDateKey, formatMonthKeyLabel } from "@/lib/date";

const PAYMENT_CALENDAR_ROUTE = "/payment/calendar";

type HomeCalendarProps = {
  /** 캔버스 폭(pt) */
  width: number;
  /** "YYYYMM" */
  month: string;
  onOpen: () => void;
};

/**
 * 방 벽의 캘린더 에셋 (FR-PAY-01·02). 방 안의 오브젝트라 카메라를 따라 함께 확대·이동하고, 자리는 방 배치(스토어)를 따른다.
 * 조회 실패는 에셋의 숫자만 감춘다 — 방과 다른 영역을 막지 않는다. (TBD: 실패 문구)
 */
function HomeCalendar({ width, month, onOpen }: HomeCalendarProps) {
  const calendar = usePaymentCalendar(month);
  // 배치 배열은 참조가 안정적이라 그대로 고르고, 사각형은 렌더에서 계산한다(셀렉터가 새 객체를 돌려주면 재렌더가 돈다).
  const placements = useRoomStore(selectPlacements);
  const rect = getWallItemRect(placements, "calendar");
  if (!calendar.data || !rect) return null;

  const upcoming = upcomingEntry(calendar.data, currentDateKey());

  return (
    <CalendarAsset
      width={width}
      rect={rect}
      monthLabel={formatMonthKeyLabel(month)}
      upcoming={upcoming ? { day: upcoming.day, name: upcoming.name, hasShortage: upcoming.preparation?.status === "SHORTAGE" } : null}
      onPress={onOpen}
    />
  );
}

type HomeCalendarPanelProps = {
  width: number;
  month: string;
  onClose: () => void;
};

/** 캘린더를 탭했을 때 열리는 출금 일정 팝오버. 카메라 밖 레이어라 확대 배율과 무관하게 그려지고, 캘린더 아래에 붙는다. */
function HomeCalendarPanel({ width, month, onClose }: HomeCalendarPanelProps) {
  const router = useRouter();
  const calendar = usePaymentCalendar(month);
  const placements = useRoomStore(selectPlacements);
  const rect = getWallItemRect(placements, "calendar");
  if (!calendar.data || !rect) return null;

  return (
    <CalendarPopover
      width={width}
      below={rect}
      calendar={calendar.data}
      monthLabel={formatMonthKeyLabel(month)}
      onClose={onClose}
      onOpenCalendar={() => router.push(PAYMENT_CALENDAR_ROUTE)}
    />
  );
}

export { HomeCalendar, HomeCalendarPanel };
export type { HomeCalendarPanelProps, HomeCalendarProps };
