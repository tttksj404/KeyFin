import * as React from "react";
import { View, type LayoutChangeEvent } from "react-native";

import { SCENE_ASPECT_RATIO } from "@/features/room/model";

type RoomSceneFrameProps = {
  /** 측정된 폭이 정해지면 그 폭으로 씬을 그린다. */
  children: (width: number) => React.ReactNode;
};

/** 부모 폭을 측정해 씬 비율(327:404)의 영역을 확보한다. 폭을 알기 전에는 비어 있다. */
function RoomSceneFrame({ children }: RoomSceneFrameProps) {
  const [width, setWidth] = React.useState(0);
  const handleLayout = React.useCallback((event: LayoutChangeEvent) => {
    setWidth(Math.round(event.nativeEvent.layout.width));
  }, []);

  return (
    <View className="w-full overflow-hidden" style={{ aspectRatio: SCENE_ASPECT_RATIO }} onLayout={handleLayout}>
      {width > 0 ? children(width) : null}
    </View>
  );
}

export { RoomSceneFrame };
export type { RoomSceneFrameProps };
