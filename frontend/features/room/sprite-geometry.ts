import type { AnchorRatio, SceneRect, SceneSize } from "@/features/room/model";

/** Expanded PNG dimensions and the previous PNG's canvas within it (all in pixels). */
export type SpriteGeometry = {
  pixelSize: SceneSize;
  contentRect: SceneRect;
};

export type FurnitureSpriteGeometry = { left: SpriteGeometry; right: SpriteGeometry; shop: SpriteGeometry };

/** Keep the old image's contain scale/centering, extending only the surrounding canvas. */
export function expandedSpriteRect(box: SceneRect, geometry: SpriteGeometry): SceneRect {
  "worklet";
  const { pixelSize, contentRect } = geometry;
  const scale = Math.min(box.width / contentRect.width, box.height / contentRect.height);
  return {
    x: box.x + (box.width - contentRect.width * scale) / 2 - contentRect.x * scale,
    y: box.y + (box.height - contentRect.height * scale) / 2 - contentRect.y * scale,
    width: pixelSize.width * scale,
    height: pixelSize.height * scale,
  };
}

/** Logical size/anchor remain unchanged for interactions, overlays and saved placements. */
export function spriteRenderView(size: SceneSize, anchor: AnchorRatio, geometry?: SpriteGeometry): {
  renderSize: SceneSize;
  renderAnchor: AnchorRatio;
} {
  if (!geometry) return { renderSize: size, renderAnchor: anchor };
  const rect = expandedSpriteRect({ x: -size.width * anchor.x, y: -size.height * anchor.y, ...size }, geometry);
  return {
    renderSize: { width: rect.width, height: rect.height },
    renderAnchor: { x: -rect.x / rect.width, y: -rect.y / rect.height },
  };
}
