import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { TransactionDetailScreen } from "@/features/transaction/components/TransactionDetailScreen";
import { parseTransactionId } from "@/features/transaction/model";

// PAGE-21 거래 상세. 거래 목록(전체보기·자산 탭 최근 거래·미확정 정리)의 행에서 들어온다.
export default function TransactionDetailRoute() {
  const { id } = useLocalSearchParams();

  return (
    <View className="flex-1 bg-background">
      <TransactionDetailScreen transactionId={parseTransactionId(id)} />
    </View>
  );
}
