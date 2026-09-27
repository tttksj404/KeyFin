import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { HomeScreen } from "@/features/home/components/HomeScreen";
import { MOVING_IN_FROM } from "@/features/room/components/MovingInScreen";

export default function HomeRoute() {
  // 입주 연출에서 넘어오면 from=moving-in 이 붙는다. 그 밖의 값은 모르는 값이라 평소 진입으로 본다.
  const { from } = useLocalSearchParams<{ from?: string }>();

  return (
    <View className="flex-1 bg-background">
      <HomeScreen arriving={from === MOVING_IN_FROM} />
    </View>
  );
}
