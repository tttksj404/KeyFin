import { View } from "react-native";

import { Text } from "@/components/ui/text";
import type { ChatMessage } from "@/features/coaching/model";
import { formatKRW } from "@/lib/money";

type CoachingBalanceTableProps = Pick<ChatMessage, "envelopeBalances">;

/** 봉투별 장부 잔액은 서버 값 그대로 표시한다. 본문에는 이 표를 설명하는 한 줄만 있다. */
export function CoachingBalanceTable({ envelopeBalances }: CoachingBalanceTableProps) {
  if (envelopeBalances.length === 0) return null;

  return (
    <View>
      <View className="flex-row items-center gap-3 border-b border-border py-2">
        <Text className="min-w-0 flex-1 text-caption text-muted-foreground">봉투</Text>
        <Text className="min-w-0 flex-1 text-right text-caption text-muted-foreground">남은 잔액</Text>
      </View>
      {envelopeBalances.map((row, index) => {
        const amount = formatKRW(row.balanceKrw);
        return (
          <View
            key={`${row.envelope}-${index}`}
            className="flex-row items-center gap-3 py-2"
            accessible
            accessibilityRole="text"
            accessibilityLabel={`${row.envelope}, 남은 잔액 ${amount}`}
          >
            <Text className="min-w-0 flex-1 text-caption text-foreground">{row.envelope}</Text>
            <Text className="min-w-0 flex-1 text-right text-caption tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
              {amount}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
