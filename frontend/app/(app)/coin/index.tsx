import { View } from "react-native";

import { CoinHistoryScreen } from "@/features/shop/components/CoinHistoryScreen";

// PAGE-30 코인 이력 (P1, FR-GAM-08). 홈 헤더 코인 배지에서 들어온다.
export default function CoinHistoryRoute() {
  return (
    <View className="flex-1 bg-background">
      <CoinHistoryScreen />
    </View>
  );
}
