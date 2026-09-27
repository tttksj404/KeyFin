import * as React from "react";
import { View, type LayoutChangeEvent } from "react-native";
import { GestureDetector } from "react-native-gesture-handler";
import Animated, { useAnimatedStyle } from "react-native-reanimated";

import { RoomCameraProvider, useRoomCameraControl } from "@/features/room/camera";
import type { SceneSize } from "@/features/room/model";
import { RoomSceneLoader } from "@/features/room/components/RoomSceneLoader";
import { SceneReadyProvider } from "@/features/room/sceneReady";
import { selectIsEditing, useRoomStore } from "@/features/room/store";

export const ROOM_VIEW_TEST_ID = "room-view";

type RoomViewProps = {
  /** 씬 영역의 접근성 라벨(예: "캐릭터가 방에 있어요") */
  accessibilityLabel: string;
  /** 방 안에 놓인 오브젝트(보드·캘린더 에셋). 캔버스 폭을 받아 씬 좌표를 환산하며 카메라를 따라 함께 확대·이동한다 */
  sceneObjects?: (width: number) => React.ReactNode;
  /** 방 위에 뜨는 UI(팝오버·코치). 카메라와 무관하게 제자리에 있고 글자 크기도 그대로다 */
  panels?: (width: number) => React.ReactNode;
  /** 참이면 카메라를 1배로 되돌리고 제스처를 끈다(팝오버가 열린 동안) */
  locked?: boolean;
  /** 확대 여부가 바뀔 때 알린다. 부모 스크롤을 잠그는 데 쓰며 참조가 안정적이어야 한다 */
  onZoomedChange?: (zoomed: boolean) => void;
  /**
   * 씬 폭을 밖에서 정한다. 생략하면 부모 폭을 재서 쓴다(기존 동작).
   * 홈은 화면을 꽉 채우려고 부모보다 넓은 폭(coverSceneWidth)을 넘기고, 넘치는 좌우는 부모가 잘라 낸다 (2026-09-18).
   */
  width?: number;
  /** 실제로 보이는 영역(pt). 방이 화면보다 넓을 때 1배 드래그 범위를 정하는 데 쓴다 */
  viewport?: SceneSize;
  /** 방 그림을 다 읽어 방을 처음 보여 줄 수 있게 됐을 때 부른다. 홈이 대기 화면을 걷는 데 쓰며 참조가 안정적이어야 한다 */
  onSceneReady?: () => void;
};

/**
 * 방 씬(캔버스)과 방 오브젝트·UI 오버레이를 겹쳐 놓은 뷰. 홈(CharacterRoom)과 방 꾸미기 화면(RoomEditScreen)이 같이 쓴다.
 * 핀치·드래그로 씬을 확대·이동하며, 편집 모드에서는 오브젝트 드래그와 겹치지 않도록 카메라를 잠근다.
 * 편집 진입 버튼·취소·완료는 여기 없다 — 홈은 RoomEditorOverlay, 편집 화면은 자기 헤더·하단 버튼이 맡는다(2026-09-15).
 */
function RoomView({
  accessibilityLabel,
  sceneObjects,
  panels,
  locked = false,
  onZoomedChange,
  width: fixedWidth,
  viewport,
  onSceneReady,
}: RoomViewProps) {
  const [measuredWidth, setMeasuredWidth] = React.useState(0);
  const width = fixedWidth ?? measuredWidth;
  const isEditing = useRoomStore(selectIsEditing);
  const { camera, gesture } = useRoomCameraControl({ width, locked: locked || isEditing, onZoomedChange, viewport });

  const handleLayout = React.useCallback((event: LayoutChangeEvent) => {
    setMeasuredWidth(Math.round(event.nativeEvent.layout.width));
  }, []);

  const cameraStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: camera.tx.value }, { translateY: camera.ty.value }, { scale: camera.scale.value }],
  }));

  return (
    <GestureDetector gesture={gesture}>
      <View
        className="relative"
        style={fixedWidth === undefined ? undefined : { width: fixedWidth }}
        onLayout={handleLayout}
        testID={ROOM_VIEW_TEST_ID}
      >
        <RoomCameraProvider value={camera}>
          <View accessible accessibilityRole="image" accessibilityLabel={accessibilityLabel}>
            <SceneReadyProvider value={onSceneReady ?? null}>
              <RoomSceneLoader />
            </SceneReadyProvider>
          </View>
        </RoomCameraProvider>
        {sceneObjects && width > 0 ? (
          <View className="absolute inset-0 overflow-hidden" pointerEvents="box-none">
            <Animated.View style={[SCENE_LAYER_STYLE, cameraStyle]} pointerEvents="box-none">
              {sceneObjects(width)}
            </Animated.View>
          </View>
        ) : null}
        {panels && width > 0 ? (
          <View className="absolute inset-0" pointerEvents="box-none">
            {panels(width)}
          </View>
        ) : null}
      </View>
    </GestureDetector>
  );
}

// pointerEvents 는 prop 으로 준다. RN Web 은 StyleSheet.create 를 거치지 않은 style 의 pointerEvents 를 버려서(2026-09-20 실측: computed auto)
// 오버레이가 방 전체의 터치를 가로챈다 — 웹의 deprecated 경고는 감수한다.
// Skia Group 의 변환 기준점이 (0,0) 이라 RN 쪽도 좌상단으로 맞춰야 두 레이어가 어긋나지 않는다.
const SCENE_LAYER_STYLE = { flex: 1, transformOrigin: "0% 0%" } as const;

export { RoomView };
export type { RoomViewProps };
