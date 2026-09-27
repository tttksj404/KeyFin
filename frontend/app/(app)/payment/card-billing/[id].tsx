import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { CardBillingDetailScreen } from "@/features/payment/components/CardBillingDetailScreen";
import { parseCardId } from "@/features/payment/model";

// PAGE-33 카드 청구 상세 (P1, FR-BGT-06). 자산 탭 카드 행과 결제 캘린더의 카드 청구 항목에서 들어온다.
export default function CardBillingDetailRoute() {
  const { id } = useLocalSearchParams();

  return (
    <View className="flex-1 bg-background">
      <CardBillingDetailScreen cardId={parseCardId(id)} />
    </View>
  );
}
