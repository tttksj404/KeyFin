import { ChevronRight } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { preparationLabel, type CalendarEntry, type PaymentCalendar } from "@/features/payment/model";
import { getSceneScale, popoverBelow, type SceneRect } from "@/features/room/model";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

// Pencil home/p0/calendar-open CalendarPopover (ZzspU): 캘린더 에셋 아래 씬 단위 폭 250, bg-card · radius lg · 날짜 행 + 링크.
// 자리는 시안의 (64,104) 고정값 대신 캘린더 스프라이트 사각형 아래로 계산한다 — 방 꾸미기에서 캘린더를 옮겨도 따라간다(2026-09-15).
export const CALENDAR_POPOVER_WIDTH = 250;
export const CALENDAR_CLOSE_LABEL = "출금 일정 닫기";
export const CALENDAR_LINK_LABEL = "캘린더 열기";
export const CALENDAR_EMPTY_MESSAGE = "이번 달 출금 예정이 없어요.";
export const ESTIMATED_SUFFIX = "(예상)";

type CalendarPopoverProps = {
  width: number;
  /** 팝오버가 붙는 캘린더 스프라이트의 씬 사각형 */
  below: SceneRect;
  calendar: PaymentCalendar;
  monthLabel: string;
  onClose: () => void;
  /** 결제 캘린더(PAGE-24)로 보낸다 */
  onOpenCalendar: () => void;
};

function CalendarPopover({ width, below, calendar, monthLabel, onClose, onOpenCalendar }: CalendarPopoverProps) {
  const scale = getSceneScale(width);
  const origin = popoverBelow(below, CALENDAR_POPOVER_WIDTH);
  const { entries, shortageCount } = calendar;
  const summary = shortageCount > 0 ? `${entries.length}건 · 부족 ${shortageCount}건` : `${entries.length}건`;

  return (
    <>
      <Pressable className="absolute inset-0" accessibilityRole="button" accessibilityLabel={CALENDAR_CLOSE_LABEL} onPress={onClose} />
      <View
        className="absolute gap-2 rounded-lg border border-border bg-card p-3.5"
        style={{ left: origin.x * scale, top: origin.y * scale, width: CALENDAR_POPOVER_WIDTH * scale }}
        accessibilityLiveRegion="polite"
      >
        <View className="flex-row items-center justify-between">
          <Text className="text-label text-foreground">{monthLabel} 출금 일정</Text>
          <Text className={cn("text-caption tabular-nums", shortageCount > 0 ? "text-destructive" : "text-card-foreground")}>{summary}</Text>
        </View>
        {entries.length > 0 ? (
          <View className="gap-1.5">
            {entries.map((entry) => (
              <EntryRow key={entry.key} entry={entry} />
            ))}
          </View>
        ) : (
          <Text className="text-body-sm text-card-foreground">{CALENDAR_EMPTY_MESSAGE}</Text>
        )}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={CALENDAR_LINK_LABEL}
          hitSlop={8}
          className="flex-row items-center gap-1 self-start active:opacity-70"
          onPress={onOpenCalendar}
        >
          <Text className="text-label text-primary">{CALENDAR_LINK_LABEL}</Text>
          <Icon as={ChevronRight} size={14} className="text-primary" />
        </Pressable>
      </View>
    </>
  );
}

// 준비 상태를 서버가 아직 계산하지 않았으면(FR-PAY-02 전) 뱃지를 그리지 않는다.
function EntryRow({ entry }: { entry: CalendarEntry }) {
  const name = entry.estimated ? `${entry.name} ${ESTIMATED_SUFFIX}` : entry.name;
  const amount = formatKRW(entry.amount);
  const badge = preparationLabel(entry.preparation);
  const prepared = entry.preparation?.status === "PREPARED";

  return (
    <View
      className="flex-row items-center gap-2"
      accessible
      accessibilityLabel={`${entry.day}일 ${name} ${amount}${badge === null ? "" : `, ${badge}`}`}
    >
      <Text className="w-8 text-caption tabular-nums text-foreground">{entry.day}일</Text>
      <View className="flex-1">
        <Text className="text-caption text-foreground" numberOfLines={1}>
          {name}
        </Text>
        <Text className="text-caption tabular-nums text-card-foreground">{amount}</Text>
      </View>
      {badge === null ? null : (
        <View className={cn("rounded-sm px-1.5 py-0.5", prepared ? "bg-positive-muted" : "bg-destructive-muted")} accessible={false}>
          <Text className={cn("text-caption tabular-nums", prepared ? "text-positive" : "text-destructive")}>{badge}</Text>
        </View>
      )}
    </View>
  );
}

export { CalendarPopover };
export type { CalendarPopoverProps };
