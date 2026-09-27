import { useRouter } from "expo-router";
import { ChevronRight } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { envelopeHealth, usedBarPercent, type Budget, type BudgetEnvelope, type BudgetTotal, type EnvelopeHealth } from "@/features/budget/model";
import { getSceneScale, popoverBelow, type SceneRect } from "@/features/room/model";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

// Pencil home/p0/board-open BoardPopover (HQKYe): 보드 에셋 아래 씬 단위 폭 250, bg-card · radius lg · 봉투 7행 + 링크.
// 자리는 시안의 (12,100) 고정값 대신 보드 스프라이트 사각형 아래로 계산한다 — 방 꾸미기에서 보드를 옮겨도 따라간다(2026-09-15).
export const BOARD_POPOVER_WIDTH = 250;
export const BOARD_CLOSE_LABEL = "보드 닫기";
export const BOARD_LINK_LABEL = "예산 탭에서 자세히";
const BUDGET_ROUTE = "/budget";

const FILL_CLASS: Record<EnvelopeHealth, string> = {
  good: "bg-positive",
  warning: "bg-warning",
  over: "bg-destructive",
  unset: "bg-muted",
};

type BoardPopoverProps = {
  width: number;
  /** 팝오버가 붙는 보드 스프라이트의 씬 사각형 */
  below: SceneRect;
  budget: Budget;
  /** "9월 1일~30일" */
  periodLabel: string;
  onClose: () => void;
};

function BoardPopover({ width, below, budget, periodLabel, onClose }: BoardPopoverProps) {
  const router = useRouter();
  const scale = getSceneScale(width);
  const origin = popoverBelow(below, BOARD_POPOVER_WIDTH);
  const summary = budget.total ? totalSummary(budget.total) : "예산 미설정";

  return (
    <>
      <Pressable className="absolute inset-0" accessibilityRole="button" accessibilityLabel={BOARD_CLOSE_LABEL} onPress={onClose} />
      <View
        className="absolute gap-2 rounded-lg border border-border bg-card p-3.5"
        style={{ left: origin.x * scale, top: origin.y * scale, width: BOARD_POPOVER_WIDTH * scale }}
        accessibilityLiveRegion="polite"
      >
        <View className="flex-row items-center justify-between">
          <Text className="text-label text-foreground">{periodLabel} 예산 보드</Text>
          <Text className={cn("text-caption tabular-nums", budget.total ? "text-primary" : "text-card-foreground")}>{summary}</Text>
        </View>
        {budget.total ? (
          <View className="gap-1.5">
            {budget.envelopes.map((envelope) => (
              <EnvelopeRow key={envelope.envelopeId} envelope={envelope} />
            ))}
          </View>
        ) : (
          <Text className="text-body-sm text-card-foreground">예산을 승인하면 봉투별 잔액이 여기에 보여요.</Text>
        )}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={BOARD_LINK_LABEL}
          onPress={() => router.push(BUDGET_ROUTE)}
          className="flex-row items-center gap-1 self-start active:opacity-70"
          hitSlop={8}
        >
          <Text className="text-label text-primary">{BOARD_LINK_LABEL}</Text>
          <Icon as={ChevronRight} size={14} className="text-primary" />
        </Pressable>
      </View>
    </>
  );
}

/** 전체 확정액이 0 이면 잔여율이 없어(null) 금액만 쓴다 */
function totalSummary(total: BudgetTotal): string {
  return total.remainingRate === null ? `${formatKRW(total.remaining)} 남음` : `${formatKRW(total.remaining)} · ${total.remainingRate}% 남음`;
}

// 확정액 0 인 봉투는 잔여율이 없어 빈 트랙이고, 쓴 돈이 있으면 over 색으로 초과 금액을 적는다(사용자 결정 2026-09-12).
function EnvelopeRow({ envelope }: { envelope: BudgetEnvelope }) {
  const health = envelopeHealth(envelope);
  const barPercent = usedBarPercent(envelope.remainingRate);
  const remainingText =
    envelope.remaining === null ? "-" : health === "over" ? `초과 ${formatKRW(envelope.remaining, { sign: "never" })}` : formatKRW(envelope.remaining);

  return (
    <View className="flex-row items-center gap-2" accessible accessibilityLabel={`${envelope.name} ${remainingText} 남음`}>
      <Text className="w-16 text-caption text-foreground" numberOfLines={1}>
        {envelope.name}
      </Text>
      <View className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <View className={cn("h-full rounded-full", FILL_CLASS[health])} style={{ width: `${barPercent}%` }} />
      </View>
      <Text className={cn("w-20 text-right text-caption tabular-nums", health === "over" ? "text-destructive" : "text-foreground")}>{remainingText}</Text>
    </View>
  );
}

export { BoardPopover };
export type { BoardPopoverProps };
