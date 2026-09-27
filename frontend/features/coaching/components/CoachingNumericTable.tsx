import { View } from "react-native";

import { Text } from "@/components/ui/text";
import type { ChatBudgetRiskRow, ChatEnvelopeSpendRow, ChatNumericRows } from "@/features/coaching/model";
import { formatKRW } from "@/lib/money";

type CoachingNumericTableProps = { numericRows: ChatNumericRows | null };

export const ENVELOPE_SPEND_TITLE = "봉투별 예상 소비";
export const BUDGET_RISK_TITLE = "봉투별 예산 초과 위험";

/**
 * 위험·가정 코칭 답변의 봉투별 표(서버 numericRows, ai/coaching/docs/chat.md numeric_rows). 값은 엔진 산출값 그대로 보여 주고 앱은 계산하지 않는다.
 * 폰 폭에 다섯 칸을 못 놓아 예산 위험은 봉투·초과 확률 한 줄 + 예산·지금까지·예상 한 줄로 접는다.
 * 소비 조회 표(CoachingSpendingTable)와 같은 캡션 타이포·경계선을 쓴다.
 */
export function CoachingNumericTable({ numericRows }: CoachingNumericTableProps) {
  if (numericRows === null) return null;
  const { envelopeSpend, budgetRisk } = numericRows;
  if (envelopeSpend.length === 0 && budgetRisk.length === 0) return null;

  return (
    <View className="gap-3">
      {envelopeSpend.length > 0 ? <EnvelopeSpendTable rows={envelopeSpend} /> : null}
      {budgetRisk.length > 0 ? <BudgetRiskTable rows={budgetRisk} /> : null}
    </View>
  );
}

/** 분위수는 '보통(p50)' 한 칸과 '낮게~높게(p10~p90)' 범위 한 칸으로 보여 준다 */
function EnvelopeSpendTable({ rows }: { rows: ChatEnvelopeSpendRow[] }) {
  return (
    <View>
      <Text className="pb-1 text-caption font-medium text-foreground">{ENVELOPE_SPEND_TITLE}</Text>
      <View className="flex-row items-center gap-3 border-b border-border py-2">
        <Text className="w-14 text-caption text-muted-foreground">봉투</Text>
        <Text className="min-w-0 flex-1 text-right text-caption text-muted-foreground">예상</Text>
        <Text className="w-32 text-right text-caption text-muted-foreground">낮게~높게</Text>
      </View>
      {rows.map((row, index) => {
        const p50 = formatKRW(row.p50Krw);
        const range = `${formatKRW(row.p10Krw, { unit: false })}~${formatKRW(row.p90Krw)}`;
        return (
          <View
            key={`${row.envelope}-${index}`}
            className="flex-row items-center gap-3 py-2"
            accessible
            accessibilityRole="text"
            accessibilityLabel={`${row.envelope}, 예상 소비 ${p50}, 낮게 ${formatKRW(row.p10Krw)}부터 높게 ${formatKRW(row.p90Krw)}까지`}
          >
            <Text className="w-14 text-caption text-foreground" numberOfLines={1}>
              {row.envelope}
            </Text>
            <Text className="min-w-0 flex-1 text-right text-caption tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
              {p50}
            </Text>
            <Text className="w-32 text-right text-caption tabular-nums text-muted-foreground" maxFontSizeMultiplier={1.3}>
              {range}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

/** 초과 확률은 서버의 0~1 값을 정수 % 로만 바꿔 보여 준다 */
export function formatOverBudgetRate(pOverBudget: number): string {
  return `${Math.round(pOverBudget * 100)}%`;
}

function BudgetRiskTable({ rows }: { rows: ChatBudgetRiskRow[] }) {
  return (
    <View>
      <Text className="pb-1 text-caption font-medium text-foreground">{BUDGET_RISK_TITLE}</Text>
      {rows.map((row, index) => {
        const rate = formatOverBudgetRate(row.pOverBudget);
        const budget = formatKRW(row.budgetKrw);
        const observed = formatKRW(row.observedUsedKrw);
        const projected = formatKRW(row.projectedUsedP50Krw);
        return (
          <View
            key={`${row.envelope}-${index}`}
            className="gap-0.5 border-t border-border py-2"
            accessible
            accessibilityRole="text"
            accessibilityLabel={`${row.envelope}, 초과 확률 ${rate}, 예산 ${budget}, 지금까지 ${observed}, 예상 ${projected}`}
          >
            <View className="flex-row items-center justify-between gap-3">
              <Text className="min-w-0 flex-1 text-caption text-foreground" numberOfLines={1}>
                {row.envelope}
              </Text>
              <Text className="text-caption tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
                초과 확률 {rate}
              </Text>
            </View>
            <Text className="text-caption tabular-nums text-muted-foreground" maxFontSizeMultiplier={1.3}>
              예산 {budget} · 지금까지 {observed} · 예상 {projected}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
