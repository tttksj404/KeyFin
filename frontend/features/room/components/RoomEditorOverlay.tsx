import { useRouter } from "expo-router";
import { Paintbrush } from "lucide-react-native";
import { View } from "react-native";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";

export const EDIT_LABEL = "방 꾸미기";
export const ROOM_EDIT_ROUTE = "/room/edit";

/**
 * 홈의 방 씬 위에 얹는 편집 진입 버튼(우상단 "꾸미기"). Pencil home/p0 (EWfx2) 에는 없는 요소라 미대조.
 * 편집 자체는 같은 자리에서 하지 않고 방 꾸미기 화면(RoomEditScreen, /room/edit)으로 간다 — 홈은 씬이 작고
 * 팝오버·코치·스크롤이 겹쳐 드래그하기 불편하다(사용자 결정 2026-09-15).
 * 2026-09-18 부터 자기 자리를 정하지 않는다: 방이 화면보다 넓어져(cover 맞춤) 방 오른쪽 끝이 화면 밖으로 나가기 때문에,
 * 부르는 쪽(홈의 사이드 버튼 줄)이 화면 기준으로 놓는다.
 * 2026-09-23 홈 사이드 버튼과 같은 게임 톤(노란 면 + 흰 테두리 + 아래쪽 음영)으로 바꿨다. RNR Button 은 그대로 두고 겉모양만 덮어쓴다.
 */
function RoomEditorOverlay() {
  const router = useRouter();

  return (
    <View pointerEvents="box-none">
      <Button
        variant="secondary"
        onPress={() => router.push(ROOM_EDIT_ROUTE)}
        accessibilityLabel={EDIT_LABEL}
        className="h-12 gap-1.5 rounded-lg border-2 border-b-4 border-white border-b-black/20 bg-warning px-4 shadow-md shadow-black/20 active:border-b-2 active:bg-warning"
      >
        <Icon as={Paintbrush} size={18} strokeWidth={2.5} className="text-warning-foreground" />
        <Text className="text-label text-warning-foreground">꾸미기</Text>
      </Button>
    </View>
  );
}

export { RoomEditorOverlay };
