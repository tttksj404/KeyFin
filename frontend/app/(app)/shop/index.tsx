import { View } from "react-native";

import { ShopScreen } from "@/features/shop/components/ShopScreen";

// PAGE-29 상점 (P1, FR-GAM-05). 홈 상점 버튼에서 들어온다.
export default function ShopRoute() {
  return (
    <View className="flex-1 bg-background">
      <ShopScreen />
    </View>
  );
}
