import { FURNITURE, roomItemThumbnailGeometry, type FurnitureId } from "@/features/room/catalog";
import { FURNITURE_GEOMETRY } from "@/features/room/furniture-geometry.generated";
import { getSpriteRect, hitTestTopmost, sceneRectToCanvas, type SceneRect } from "@/features/room/model";
import { placementView, type Placement } from "@/features/room/scene";
import { expandedSpriteRect, spriteRenderView, type SpriteGeometry } from "@/features/room/sprite-geometry";
import { penaltyGeometry } from "@/features/room/penalties";
import { stickerGeometry } from "@/features/room/stickers";

function expectRect(actual: SceneRect, expected: SceneRect) {
  for (const field of ["x", "y", "width", "height"] as const) expect(actual[field]).toBeCloseTo(expected[field], 8);
}

describe("expanded sprite geometry", () => {
  const asymmetric: SpriteGeometry = {
    pixelSize: { width: 148, height: 232 },
    contentRect: { x: 12, y: 8, width: 100, height: 200 },
  };

  it("preserves contain centering with asymmetric padding and a different box aspect ratio", () => {
    expectRect(expandedSpriteRect({ x: 10, y: 20, width: 90, height: 80 }, asymmetric), {
      x: 30.2, y: 16.8, width: 59.2, height: 92.8,
    });
  });

  it("preserves vertical letterboxing as well as horizontal letterboxing", () => {
    expectRect(expandedSpriteRect({ x: 10, y: 20, width: 50, height: 140 }, asymmetric), {
      x: 4, y: 36, width: 74, height: 116,
    });
  });

  it("keeps existing geometry for sprites without expansion metadata", () => {
    const size = { width: 30, height: 45 };
    const anchor = { x: 0.5, y: 0.7 };
    expect(spriteRenderView(size, anchor)).toEqual({ renderSize: size, renderAnchor: anchor });
    expect(roomItemThumbnailGeometry("refrigerator_original")).toBeUndefined();
    expect(roomItemThumbnailGeometry("board_default")).toBeUndefined();
    expect(roomItemThumbnailGeometry("unknown")).toBeUndefined();
    const wall = placementView({ itemId: "board", anchor: { x: 100, y: 100 } });
    expect(wall.renderSize).toEqual(wall.size);
    expect(wall.renderAnchor).toEqual(wall.anchor);
  });
});

// Baseline body measurements are deliberately independent of the generated shadow bounds.
const BODY = {
  bed: [174.3, 143.3, 0.684], sofa: [131.7, 112.2, 0.695], coffee_table: [74.9, 57.8, 0.662],
  desk: [108.6, 95.9, 0.706], dining_table: [103.8, 92.9, 0.709], dining_chair: [55.2, 79.8, 0.819],
  bookcase: [59.7, 120.8, 0.871], nightstand: [44.1, 48.4, 0.762], tv_set: [97.1, 115.6, 0.781],
} as const;

describe("shadow catalog integration", () => {
  it("covers exactly the 36 approved furniture variants", () => {
    const expected = Object.keys(BODY).flatMap((kind) => ["original", "black", "pink", "sunset"].map((color) => `${kind}_${color}`));
    expect(Object.keys(FURNITURE_GEOMETRY).sort()).toEqual(expected.sort());
  });

  it.each(Object.entries(FURNITURE_GEOMETRY))("%s preserves its body rect across directions, moves and zoom levels", (key, geometry) => {
    const itemId = key as FurnitureId;
    const kind = key.replace(/_(original|black|pink|sunset)$/, "") as keyof typeof BODY;
    const [width, height, anchorY] = BODY[kind];
    for (const direction of ["FRONT_RIGHT", "FRONT_LEFT"] as const) {
      const view = FURNITURE[itemId].views[direction];
      const data = geometry[direction === "FRONT_RIGHT" ? "left" : "right"];
      expect(view.size).toEqual({ width: kind === "tv_set" && direction === "FRONT_LEFT" ? 97.5 : width, height });
      expect(view.anchor).toEqual({ x: 0.5, y: anchorY });
      for (const anchor of [{ x: 160, y: 400 }, { x: 121.625, y: 538 }]) {
        const bodyBox = getSpriteRect(anchor, view.size, view.anchor);
        const render = getSpriteRect(anchor, view.renderSize, view.renderAnchor);
        const pixelsToScene = Math.min(bodyBox.width / data.contentRect.width, bodyBox.height / data.contentRect.height);
        const oldVisible = {
          x: bodyBox.x + (bodyBox.width - data.contentRect.width * pixelsToScene) / 2,
          y: bodyBox.y + (bodyBox.height - data.contentRect.height * pixelsToScene) / 2,
          width: data.contentRect.width * pixelsToScene, height: data.contentRect.height * pixelsToScene,
        };
        const bodyWithinExpanded = {
          x: render.x + data.contentRect.x * render.width / data.pixelSize.width,
          y: render.y + data.contentRect.y * render.height / data.pixelSize.height,
          width: data.contentRect.width * render.width / data.pixelSize.width,
          height: data.contentRect.height * render.height / data.pixelSize.height,
        };
        for (const zoom of [0.75, 1, 2]) expectRect(sceneRectToCanvas(bodyWithinExpanded, zoom), sceneRectToCanvas(oldVisible, zoom));
      }
      expect(placementView({ itemId, direction, anchor: { x: 160, y: 400 } })).toMatchObject(view);
    }
  });

  it.each([
    ["sofa_default", "sofa_original"], ["tv_default", "tv_set_original"], ["fridge_default", "refrigerator_original"],
  ] as const)("%s shares rendering and thumbnail geometry with %s", (alias, original) => {
    expect(FURNITURE[alias].views).toEqual(FURNITURE[original].views);
    expect(roomItemThumbnailGeometry(alias)).toEqual(roomItemThumbnailGeometry(original));
  });

  it("does not extend interaction bounds into the new shadow canvas", () => {
    const view = FURNITURE.coffee_table_original.views.FRONT_RIGHT;
    const anchor = { x: 160, y: 400 };
    const body = getSpriteRect(anchor, view.size, view.anchor);
    const render = getSpriteRect(anchor, view.renderSize, view.renderAnchor);
    expect(render.x).toBeLessThan(body.x);
    const shadowPoint = { x: (render.x + body.x) / 2, y: body.y + body.height / 2 };
    expect(hitTestTopmost(shadowPoint, [{ id: "coffee", rect: body }])).toBeNull();
    expect(hitTestTopmost({ x: body.x + body.width / 2, y: body.y + body.height / 2 }, [{ id: "coffee", rect: body }])).toBe("coffee");
  });

  it("overlay placement is independent of expanded render bounds", () => {
    const placement: Placement = { itemId: "dining_table_black", anchor: { x: 160, y: 330 }, direction: "FRONT_RIGHT" };
    const view = FURNITURE.dining_table_black.views.FRONT_RIGHT;
    const sticker = stickerGeometry(placement);
    const penalty = penaltyGeometry(placement, [1]);
    const previous = { renderSize: view.renderSize, renderAnchor: view.renderAnchor };
    try {
      view.renderSize = { width: view.renderSize.width * 2, height: view.renderSize.height * 3 };
      view.renderAnchor = { x: 0.1, y: 0.2 };
      expect(stickerGeometry(placement)).toEqual(sticker);
      expect(penaltyGeometry(placement, [1])).toEqual(penalty);
    } finally { Object.assign(view, previous); }
  });
});
