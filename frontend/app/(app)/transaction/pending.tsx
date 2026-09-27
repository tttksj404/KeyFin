import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { PendingCleanupScreen } from "@/features/transaction/components/PendingCleanupScreen";
import { toFocusTransactionId } from "@/features/transaction/model";

// PAGE-22 미확정 정리. 저녁 21:00 CLEANUP 푸시의 진입점이다 (docs/frontend-spec.md §3).
// "새로 정리할 거래가 있어요" 알림에서 오면 focus=<거래 id> 가 붙고, 그 거래의 분류 창을 바로 열어 준다.
export default function PendingCleanupRoute() {
  const { focus } = useLocalSearchParams<{ focus?: string }>();

  return (
    <View className="flex-1 bg-background">
      <PendingCleanupScreen focusId={toFocusTransactionId(focus)} />
    </View>
  );
}
