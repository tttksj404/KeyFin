import { SafeAreaView } from "react-native-safe-area-context";

import { MovingInScreen } from "@/features/room/components/MovingInScreen";

// PAGE-08 캐릭터 입주중. 예산 승인(PAGE-07) 뒤 방 데이터를 받는 동안 보여준다.
export default function MovingInRoute() {
  return (
    <SafeAreaView className="flex-1 bg-background" edges={["top", "bottom"]}>
      <MovingInScreen />
    </SafeAreaView>
  );
}
