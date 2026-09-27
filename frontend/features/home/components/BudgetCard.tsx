import { View } from "react-native";

import { CountUpAmount } from "@/components/ui/count-up-amount";
import { Text } from "@/components/ui/text";
import { EnvelopeChart } from "@/features/budget/components/EnvelopeChart";
import { budgetHealth, usedBarPercent, type BudgetEnvelope, type BudgetHealth, type BudgetTotal } from "@/features/budget/model";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

// Pencil home/p0 (EWfx2) BudgetCard (sMRC0): bg-primary · radius 20 · padding 20 · gap 16 · 진행 바 8pt(→ 24pt, 2026-09-23 사용자 요청으로 두 번 키움) · 봉투 7종 사용률 세로 막대.
// good 문구 "좋아요!" 는 Pencil, warning/over 문구는 임시. (TBD)
const HEALTH_STYLE: Record<BudgetHealth, { label: string; textClassName: string; barClassName: string }> = {
  good: { label: "좋아요!", textClassName: "text-positive", barClassName: "bg-positive" },
  warning: { label: "조금만 아껴요", textClassName: "text-warning", barClassName: "bg-warning" },
  over: { label: "예산 초과", textClassName: "text-destructive", barClassName: "bg-destructive" },
};

type BudgetCardProps = {
  total: BudgetTotal;
  envelopes: BudgetEnvelope[];
  onSelectEnvelope?: (envelopeId: number) => void;
  /** 현재 주기 "9월 1일~30일". 주기가 달력 월과 다를 수 있어 "이번 달" 대신 기간을 쓴다 */
  period: string;
};

function BudgetCard({ total, envelopes, period, onSelectEnvelope }: BudgetCardProps) {
  const health = HEALTH_STYLE[budgetHealth(total)];
  const usedPercent = usedBarPercent(total.remainingRate);

  return (
    <View className="gap-4 rounded-xl bg-primary p-5">
      <View className="flex-row items-center justify-between">
        <View className="gap-0.5">
          <Text className="text-h3 text-primary-foreground">남은 예산</Text>
          <Text className="text-caption tabular-nums text-primary-foreground">{period}</Text>
        </View>
        <Text className={cn("text-caption", health.textClassName)}>{health.label}</Text>
      </View>
      <View className="gap-1">
        <CountUpAmount value={total.remaining} className="text-display tabular-nums text-primary-foreground" />
        <Text className="text-caption text-primary-foreground">
          총 예산 {formatKRW(total.confirmed)} 중 {formatKRW(total.spent)} 사용
        </Text>
      </View>
      <View
        className="h-6 w-full overflow-hidden rounded-full bg-accent"
        accessible
        accessibilityRole="progressbar"
        accessibilityLabel="예산 사용률"
        accessibilityValue={{ min: 0, max: 100, now: usedPercent }}
      >
        <View className={cn("h-full rounded-full", health.barClassName)} style={{ width: `${usedPercent}%` }} />
      </View>
      <EnvelopeChart envelopes={envelopes} onSelect={onSelectEnvelope} />
    </View>
  );
}

export { BudgetCard };
export type { BudgetCardProps };
