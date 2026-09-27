import { Image, View } from "react-native";

import { expandedSpriteRect, type SpriteGeometry } from "@/features/room/sprite-geometry";

type FurnitureThumbnailProps = {
  source: number;
  geometry?: SpriteGeometry;
  /** 그림자 확장 전 PNG를 contain 하던 정사각 표시 영역. */
  size: number;
};

/** 본체의 크기와 중앙 정렬은 유지하고 그림자 여백만 기존 표시 영역 밖으로 그린다. */
function FurnitureThumbnail({ source, geometry, size }: FurnitureThumbnailProps) {
  const box = { x: 0, y: 0, width: size, height: size };
  const rect = geometry === undefined ? box : expandedSpriteRect(box, geometry);

  return (
    <View style={{ width: size, height: size, overflow: "visible" }} pointerEvents="none" accessible={false}>
      <Image
        source={source}
        style={{ position: "absolute", left: rect.x, top: rect.y, width: rect.width, height: rect.height }}
        resizeMode="contain"
        accessible={false}
      />
    </View>
  );
}

export { FurnitureThumbnail };
