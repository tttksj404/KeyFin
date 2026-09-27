import { render } from "@testing-library/react-native";
import * as React from "react";

import { FurnitureThumbnail } from "@/features/room/components/FurnitureThumbnail";
import type { SpriteGeometry } from "@/features/room/sprite-geometry";

const source = require("@/assets/sprites/furniture/sofa_black/shop.png");

describe("가구 썸네일 그림자 확장", () => {
  it.each([
    {
      size: 72,
      geometry: { pixelSize: { width: 240, height: 140 }, contentRect: { x: 8, y: 4, width: 200, height: 100 } },
      // 기존 200×100 본체는 72×36, 위쪽 contain 여백은 18이다.
      rect: { left: -2.88, top: 16.56, width: 86.4, height: 50.4 },
    },
    {
      size: 48,
      geometry: { pixelSize: { width: 140, height: 232 }, contentRect: { x: 8, y: 20, width: 100, height: 200 } },
      // 기존 100×200 본체는 24×48, 왼쪽 contain 여백은 12이다.
      rect: { left: 10.08, top: -4.8, width: 33.6, height: 55.68 },
    },
  ] satisfies { size: number; geometry: SpriteGeometry; rect: { left: number; top: number; width: number; height: number } }[])(
    "$size px에서 비대칭 그림자 여백을 늘려도 기존 본체 크기와 contain 중앙 정렬을 유지한다",
    async ({ size, geometry, rect }) => {
      const view = await render(<FurnitureThumbnail source={source} geometry={geometry} size={size} />);

      expect(view.toJSON()).toMatchObject({
        props: {
          style: { width: size, height: size, overflow: "visible" },
          pointerEvents: "none",
          accessible: false,
        },
        children: [{
          props: {
            style: {
              position: "absolute",
              left: expect.closeTo(rect.left),
              top: expect.closeTo(rect.top),
              width: expect.closeTo(rect.width),
              height: expect.closeTo(rect.height),
            },
            resizeMode: "contain",
            accessible: false,
          },
        }],
      });
    }
  );

  it.each([48, 72])("메타데이터가 없는 가구는 기존 %s px contain 표시를 유지한다", async (size) => {
    const view = await render(<FurnitureThumbnail source={source} size={size} />);

    expect(view.toJSON()).toMatchObject({
      props: { style: { width: size, height: size, overflow: "visible" }, pointerEvents: "none" },
      children: [{ props: { style: { left: 0, top: 0, width: size, height: size }, resizeMode: "contain" } }],
    });
  });
});
