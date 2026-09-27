import { FURNITURE, furnitureGroupOf, hangsOnWall, roomItemIdByAssetKey, type FurnitureId } from "@/features/room/catalog";
import { FURNITURE_SPRITES } from "@/features/room/furniture-sprites";
import {
  DEFAULT_LAYOUT,
  facingOf,
  flipPlacement,
  getWalkBlockers,
  isPlaceableOn,
  occupantOf,
  occupantsCollide,
  placeNewItem,
  placementView,
  type Placement,
} from "@/features/room/scene";

/** 배치가 놓일 수 있는 자리이고 다른 것과 겹치지 않는지 */
function expectSettled(placements: readonly Placement[], itemId: FurnitureId) {
  const target = placements.find((placement) => placement.itemId === itemId);
  if (target === undefined) throw new Error(`${itemId} 가 배치에 없다`);
  const occupant = occupantOf(target);
  expect(isPlaceableOn(occupant.surface, occupant.cell, occupant.footprint)).toBe(true);
  for (const other of placements) {
    if (other.itemId !== itemId) expect(occupantsCollide(occupant, occupantOf(other))).toBe(false);
  }
}

describe("가구 카탈로그", () => {
  it("그림이 있는 가구와 기존 서버 assetKey 별칭 3종이 모두 있고, 방향마다 그림·크기가 있다", () => {
    const ids = [...Object.keys(FURNITURE_SPRITES), "sofa_default", "fridge_default", "tv_default"];

    expect(Object.keys(FURNITURE).sort()).toEqual(ids.sort());
    for (const item of Object.values(FURNITURE)) {
      expect(item.assetKey).toBe(item.id);
      expect(item.grid.w).toBeGreaterThan(0);
      expect(item.grid.d).toBeGreaterThan(0);
      for (const view of Object.values(item.views)) {
        expect(view.size.width).toBeGreaterThan(0);
        expect(view.anchor.x).toBeGreaterThan(0);
        expect(view.anchor.x).toBeLessThan(1);
      }
    }
  });

  it("기본 가구는 오리지널 그림을 쓰고, assetKey 로 가구·분류를 찾는다", () => {
    expect(FURNITURE.sofa_default.views.FRONT_RIGHT.sprite).toBe(FURNITURE.sofa_original.views.FRONT_RIGHT.sprite);
    expect(roomItemIdByAssetKey("tv_default")).toBe("tv_default");
    expect(roomItemIdByAssetKey("board_default")).toBe("board");
    expect(furnitureGroupOf("bed_black")).toBe("bed");
    expect(furnitureGroupOf("plant_monstera_terracotta")).toBe("plant");
    expect(furnitureGroupOf("board_default")).toBeNull();
    expect(furnitureGroupOf("sofa_blue")).toBeNull();
    expect(hangsOnWall("window_sky_clouds")).toBe(true);
    expect(hangsOnWall("board")).toBe(true);
    expect(hangsOnWall("desk_pink")).toBe(false);
  });
});

describe("방향과 발자국", () => {
  it("바닥 가구는 FRONT_LEFT 로 돌면 반대쪽 그림을 쓰고 발자국 가로·세로가 바뀐다", () => {
    const right: Placement = { itemId: "sofa_pink", anchor: { x: 160, y: 450 } };
    const left: Placement = { ...right, direction: "FRONT_LEFT" };

    expect(placementView(right).sprite).toBe(FURNITURE.sofa_pink.views.FRONT_RIGHT.sprite);
    expect(placementView(left).sprite).toBe(FURNITURE.sofa_pink.views.FRONT_LEFT.sprite);
    expect(placementView(left).grid).toEqual({ w: placementView(right).grid.d, d: placementView(right).grid.w });
  });

  it("벽 장식은 붙은 벽이 방향을 정하고 벽 칸 모양은 그대로다", () => {
    const onLeft: Placement = { itemId: "window_sky_clouds", surface: "WALL_LEFT", anchor: { x: 60, y: 150 } };
    const onRight: Placement = { ...onLeft, surface: "WALL_RIGHT", direction: "FRONT_RIGHT" };

    expect(facingOf(onLeft)).toBe("FRONT_RIGHT");
    expect(facingOf(onRight)).toBe("FRONT_LEFT");
    expect(placementView(onRight).sprite).toBe(FURNITURE.window_sky_clouds.views.FRONT_LEFT.sprite);
    expect(placementView(onRight).grid).toEqual(placementView(onLeft).grid);
  });

  it("러그는 가구와 겹쳐도 되고 캐릭터 길을 막지 않는다", () => {
    const sofa = DEFAULT_LAYOUT.find((placement) => placement.itemId === "sofa_default")!;
    const rug: Placement = { itemId: "decor_checker_rug", anchor: sofa.anchor };

    expect(occupantsCollide(occupantOf(rug), occupantOf(sofa))).toBe(false);
    expect(occupantsCollide(occupantOf(rug), occupantOf({ itemId: "decor_oval_rug", anchor: sofa.anchor }))).toBe(true);
    expect(getWalkBlockers([...DEFAULT_LAYOUT, rug])).toHaveLength(getWalkBlockers(DEFAULT_LAYOUT).length);
  });
});

describe("flipPlacement — 방향 바꾸기", () => {
  it("바닥 가구는 제자리 근처에서 돌고, 두 번 돌리면 원래 방향이다", () => {
    const once = flipPlacement(DEFAULT_LAYOUT, "sofa_default");
    if (once === null) throw new Error("소파를 돌릴 자리가 없다");

    expect(once.find((placement) => placement.itemId === "sofa_default")).toMatchObject({ direction: "FRONT_LEFT" });
    expectSettled(once, "sofa_default");

    const twice = flipPlacement(once, "sofa_default");
    expect(twice?.find((placement) => placement.itemId === "sofa_default")).not.toHaveProperty("direction");
  });

  it("벽 장식은 맞은편 벽으로 옮겨 건다", () => {
    const placed = placeNewItem(DEFAULT_LAYOUT, "decor_round_mirror");
    if (placed === null) throw new Error("거울을 걸 자리가 없다");
    const flipped = flipPlacement([...DEFAULT_LAYOUT, placed], "decor_round_mirror");

    expect(placed.surface).toBe("WALL_LEFT");
    expect(flipped?.find((placement) => placement.itemId === "decor_round_mirror")?.surface).toBe("WALL_RIGHT");
    expectSettled(flipped ?? [], "decor_round_mirror");
  });

  it("예산 보드·캘린더와 배치에 없는 것은 돌리지 않는다", () => {
    expect(flipPlacement(DEFAULT_LAYOUT, "board")).toBeNull();
    expect(flipPlacement(DEFAULT_LAYOUT, "bed_black")).toBeNull();
  });
});

describe("placeNewItem — 보관함에서 꺼내 놓기", () => {
  it("바닥 가구는 빈 바닥 칸에 FRONT_RIGHT 로 놓고 보유 가구 id 를 잇는다", () => {
    const placement = placeNewItem(DEFAULT_LAYOUT, "bed_pink", 210);
    if (placement === null) throw new Error("침대를 놓을 자리가 없다");

    expect(placement).toMatchObject({ itemId: "bed_pink", userFurnitureId: 210 });
    expect(placement).not.toHaveProperty("surface");
    expect(placement).not.toHaveProperty("direction");
    expectSettled([...DEFAULT_LAYOUT, placement], "bed_pink");
  });

  it("벽 장식은 왼쪽 벽부터 채우고, 차면 오른쪽 벽, 둘 다 차면 null 이다", () => {
    // 같은 창문을 여러 번 걸어 벽 칸만 채운다 — 자리 찾기는 id 와 무관하게 차지한 칸을 피한다
    const placements: Placement[] = [...DEFAULT_LAYOUT];
    for (let attempt = 0; attempt < 40; attempt++) {
      const next = placeNewItem(placements, "window_sky_clouds");
      if (next === null) break;
      placements.push(next);
    }

    expect(placeNewItem(DEFAULT_LAYOUT, "window_sky_clouds")?.surface).toBe("WALL_LEFT");
    expect(placements.some((placement) => placement.itemId === "window_sky_clouds" && placement.surface === "WALL_RIGHT")).toBe(true);
    expect(placeNewItem(placements, "window_sky_clouds")).toBeNull();
  });
});
