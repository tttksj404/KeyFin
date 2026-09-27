import { View } from "react-native";

import { WardrobeScreen } from "@/features/room/components/WardrobeScreen";

// 옷장 (P1, FR-GAM-05 장착). 홈 옷장 버튼에서 들어온다.
export default function WardrobeRoute() {
  return (
    <View className="flex-1 bg-background">
      <WardrobeScreen />
    </View>
  );
}
