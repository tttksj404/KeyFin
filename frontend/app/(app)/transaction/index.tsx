import { View } from "react-native";

import { TransactionListScreen } from "@/features/transaction/components/TransactionListScreen";

// 거래 내역 전체보기. 자산 탭(PAGE-11) "전체보기"에서 들어온다. 필터는 검색 파라미터(month·envelopeId·accountId·cardId).
export default function TransactionListRoute() {
  return (
    <View className="flex-1 bg-background">
      <TransactionListScreen />
    </View>
  );
}
