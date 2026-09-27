import { View } from "react-native";

import { Text } from "@/components/ui/text";
import type { ChatMessage } from "@/features/coaching/model";
import { formatKRW } from "@/lib/money";

type CoachingSpendingTableProps = Pick<ChatMessage, "rows" | "totalKrw">;

/** 소비 집계는 서버 값 그대로 표시한다. 빈 조회(rows [], totalKrw "0")도 합계는 보여 준다. */
export function CoachingSpendingTable({ rows, totalKrw }: CoachingSpendingTableProps) {
  if (rows.length === 0 && totalKrw === null) return null;

  return (
    <View>
      {rows.length > 0 ? (
        <>
          <View className="flex-row items-center gap-3 border-b border-border py-2">
            <Text className="min-w-0 flex-1 text-caption text-muted-foreground">봉투</Text>
            <Text className="min-w-0 flex-1 text-right text-caption text-muted-foreground">소비 금액</Text>
            <Text className="w-12 text-right text-caption text-muted-foreground">건수</Text>
          </View>
          {rows.map((row, index) => {
            const amount = formatKRW(row.totalKrw);
            return (
              <View
                key={`${row.envelope}-${index}`}
                className="flex-row items-center gap-3 py-2"
                accessible
                accessibilityRole="text"
                accessibilityLabel={`${row.envelope}, 소비 금액 ${amount}, ${row.count}건`}
              >
                <Text className="min-w-0 flex-1 text-caption text-foreground">{row.envelope}</Text>
                <Text className="min-w-0 flex-1 text-right text-caption tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
                  {amount}
                </Text>
                <Text className="w-12 text-right text-caption tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
                  {row.count}건
                </Text>
              </View>
            );
          })}
        </>
      ) : null}
      {totalKrw !== null ? (
        <View className="flex-row items-center justify-between gap-3 border-t border-border py-2">
          <Text className="text-caption text-foreground">합계</Text>
          <Text className="min-w-0 shrink text-right text-caption tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
            {formatKRW(totalKrw)}
          </Text>
        </View>
      ) : null}
    </View>
  );
}
