import { Pressable, View } from "react-native";

import { Badge } from "@/components/ui/badge";
import { Text } from "@/components/ui/text";
import { isIncoming, merchantLabel, transactionBadge, transactionCategoryLabel, type Transaction } from "@/features/transaction/model";
import { formatMonthDay, parseKSTDateKey } from "@/lib/date";
import { formatKRW, subtractKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

type TransactionRowProps = {
  transaction: Transaction;
  /** 거래 상세(PAGE-21)로 보낸다 */
  onPress: () => void;
};

// Pencil TransactionRow (자산관리 cu9o6): 가맹점 + "날짜 · 분류" / 우측 금액, 아래 구분선.
// 들어온 돈은 + 와 positive 색, 나간 돈은 − 로 쓴다. 취소 거래는 금액에 취소선을 긋는다.
function TransactionRow({ transaction, onPress }: TransactionRowProps) {
  const incoming = isIncoming(transaction);
  const badge = transactionBadge(transaction);
  const canceled = transaction.status === "CANCELED";
  const amount = incoming
    ? formatKRW(transaction.amount, { sign: "always" })
    : formatKRW(subtractKRW("0", transaction.amount));
  const meta = `${formatMonthDay(parseKSTDateKey(transaction.txDate))} · ${transactionCategoryLabel(transaction)}`;

  return (
    <Pressable
      className="min-h-touch flex-row items-center justify-between gap-3 border-b border-border py-3 active:opacity-70"
      accessible
      accessibilityRole="button"
      accessibilityLabel={[merchantLabel(transaction), meta, amount, badge].filter(Boolean).join(", ")}
      accessibilityHint="거래 상세를 엽니다"
      onPress={onPress}
    >
      <View className="flex-1 gap-1">
        <Text className="text-h3 text-foreground" numberOfLines={1}>
          {merchantLabel(transaction)}
        </Text>
        <View className="flex-row items-center gap-1.5">
          <Text className="shrink text-caption text-card-foreground" numberOfLines={1}>
            {meta}
          </Text>
          {badge === null ? null : (
            <Badge variant="secondary">
              <Text>{badge}</Text>
            </Badge>
          )}
        </View>
      </View>
      <Text
        className={cn(
          "text-amount-sm tabular-nums",
          incoming ? "text-positive" : "text-foreground",
          canceled && "text-card-foreground line-through"
        )}
        maxFontSizeMultiplier={1.3}
      >
        {amount}
      </Text>
    </Pressable>
  );
}

export { TransactionRow };
