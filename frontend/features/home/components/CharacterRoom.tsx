import * as React from "react";
import { View } from "react-native";

import { RoomView, type RoomViewProps } from "@/features/room/components/RoomView";

// Pencil home/p0 (EWfx2) CharacterRoom. 가입 시 기본 착장이 지급되므로 빈 방 상태는 없다 (결정 2026-09-08).
// 2026-09-15 사용자 결정: 방을 편집 화면처럼 화면 폭 가득 키운다(좌우 여백 없음). 예산 카드는 홈에서 빠지고 리스트 탭 → 예산 시트.
export const ROOM_LABEL = "캐릭터가 방에 있어요";

type CharacterRoomProps = Pick<RoomViewProps, "sceneObjects" | "panels" | "locked" | "onZoomedChange" | "width" | "viewport" | "onSceneReady">;

function CharacterRoom(props: CharacterRoomProps) {
  return (
    <View>
      <RoomView accessibilityLabel={ROOM_LABEL} {...props} />
    </View>
  );
}

export { CharacterRoom };
export type { CharacterRoomProps };
