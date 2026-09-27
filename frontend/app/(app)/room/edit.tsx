import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { EDIT_FROM_SHOP, RoomEditScreen } from "@/features/room/components/RoomEditScreen";

// 방 꾸미기. 홈 방 씬의 '꾸미기' 버튼에서 들어와 가구·벽 오브젝트를 옮기고 완료하면 홈으로 돌아간다.
// 상점에서 가구를 사고 넘어오면 from=shop 이 붙는다 — 방금 산 가구를 놓으러 온 것이라 보관함을 펴 둔 채로 연다.
export default function RoomEditRoute() {
  const { from } = useLocalSearchParams<{ from?: string }>();

  return (
    <View className="flex-1 bg-background">
      <RoomEditScreen openStorage={from === EDIT_FROM_SHOP} />
    </View>
  );
}
