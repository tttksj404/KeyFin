import {
  statusOfSurface,
  surfaceOfStatus,
  toPlacement,
  toPlacementRequest,
  toPlacements,
} from "@/features/room/furniture";
import type { PlacedFurnitureDto } from "@/features/room/model";
import { FURNITURE } from "@/features/room/catalog";
import { anchorToCell, cellAnchor, cellsOverlap } from "@/features/room/grid";
import { DEFAULT_LAYOUT, SURFACES, isPlaceableOnFloor, placementView, withDefaultWallItems, type Placement } from "@/features/room/scene";

const sofa: PlacedFurnitureDto = {
  userFurnitureId: 204,
  itemId: 4,
  slotType: "FLOOR",
  assetKey: "sofa_default",
  placementStatus: "FLOOR",
  placementDirection: "FRONT_RIGHT",
  positionX: 165,
  positionY: 280,
  layer: 0,
  defaultFurnitureType: "SOFA",
  furnitureType: "SOFA",
  stickerAttached: false,
  canUnplace: false,
};

const board: PlacedFurnitureDto = {
  ...sofa,
  userFurnitureId: 205,
  assetKey: "board_default",
  slotType: "WALL",
  placementStatus: "RIGHT_WALL",
  positionX: 240,
  positionY: 90,
  defaultFurnitureType: null,
  furnitureType: null,
  canUnplace: true,
};

const windowOnWall: PlacedFurnitureDto = { ...board, userFurnitureId: 207, assetKey: "window_sky_clouds", placementStatus: "LEFT_WALL", positionX: 60 };

describe("설치 면 ↔ 씬 면", () => {
  it("서버 값과 씬 면을 양방향으로 옮긴다", () => {
    expect(surfaceOfStatus("LEFT_WALL")).toBe("WALL_LEFT");
    expect(surfaceOfStatus("RIGHT_WALL")).toBe("WALL_RIGHT");
    expect(surfaceOfStatus("FLOOR")).toBe("FLOOR");
    expect(surfaceOfStatus("CEILING")).toBeNull();

    expect(statusOfSurface("WALL_LEFT")).toBe("LEFT_WALL");
    expect(statusOfSurface(undefined)).toBe("FLOOR");
  });
});

describe("toPlacement — 서버 가구를 씬 배치로", () => {
  it("바닥 가구는 면 없이, 벽 가구는 자기 벽으로 놓는다", () => {
    expect(toPlacement(sofa)).toEqual({ itemId: "sofa_default", userFurnitureId: 204, anchor: { x: 165, y: 280 }, layer: 0 });
    expect(toPlacement(board)).toEqual({
      itemId: "board",
      userFurnitureId: 205,
      anchor: { x: 240, y: 90 },
      layer: 0,
      surface: "WALL_RIGHT",
    });
    expect(toPlacement(windowOnWall)).toMatchObject({ itemId: "window_sky_clouds", surface: "WALL_LEFT" });
  });

  it("바닥 가구는 서버 방향을 따르고 FRONT_RIGHT 는 생략형이다 — 모르는 값은 FRONT_RIGHT, 벽에 걸린 것은 방향을 두지 않는다", () => {
    expect(toPlacement({ ...sofa, placementDirection: "FRONT_LEFT" })).toMatchObject({ direction: "FRONT_LEFT" });
    expect(toPlacement({ ...sofa, placementDirection: "BACK" })).not.toHaveProperty("direction");
    expect(toPlacement({ ...windowOnWall, placementDirection: "FRONT_LEFT" })).not.toHaveProperty("direction");
  });

  it("그릴 수 없는 항목은 null 이다 — 모르는 assetKey · 면 불일치 · 씬 밖 좌표", () => {
    expect(toPlacement({ ...sofa, assetKey: "sofa_blue" })).toBeNull();
    expect(toPlacement({ ...sofa, placementStatus: "RIGHT_WALL" })).toBeNull();
    expect(toPlacement({ ...board, placementStatus: "FLOOR" })).toBeNull();
    expect(toPlacement({ ...windowOnWall, placementStatus: "FLOOR" })).toBeNull();
    expect(toPlacement({ ...sofa, positionY: 999 })).toBeNull();
  });

  it("목록은 그릴 수 있는 것만 남긴다", () => {
    expect(toPlacements([sofa, { ...board, assetKey: "unknown_key" }])).toHaveLength(1);
  });

  it("옛 방 좌표처럼 바닥 밖에 저장된 가구는 가장 가까운 빈 칸에 앉힌다", () => {
    const fridge: PlacedFurnitureDto = { ...sofa, userFurnitureId: 206, assetKey: "fridge_default", positionX: 170, positionY: 275 };
    const settled = toPlacements([sofa, fridge]);
    const footprints = settled.map((placement) => placementView(placement).grid);
    const cells = settled.map((placement, index) => anchorToCell(SURFACES.FLOOR, placement.anchor, footprints[index]));

    expect(settled.map((placement) => placement.userFurnitureId)).toEqual([204, 206]);
    cells.forEach((cell, index) => {
      expect(isPlaceableOnFloor(cell, footprints[index])).toBe(true);
      expect(settled[index].anchor).toEqual(cellAnchor(SURFACES.FLOOR, cell, footprints[index]));
    });
    expect(cellsOverlap(cells[0], footprints[0], cells[1], footprints[1])).toBe(false);
  });

  it("이미 제자리인 가구는 그대로 둔다", () => {
    const anchor = cellAnchor(SURFACES.FLOOR, { col: 6, row: 4 }, FURNITURE.sofa_default.grid);

    expect(toPlacements([{ ...sofa, positionX: anchor.x, positionY: anchor.y }])[0].anchor).toEqual(anchor);
  });
});

describe("withDefaultWallItems — 서버에 없는 벽 오브젝트를 기본 자리에 채운다", () => {
  const sofaOnFloor: Placement = {
    itemId: "sofa_default",
    userFurnitureId: 204,
    anchor: cellAnchor(SURFACES.FLOOR, { col: 6, row: 4 }, FURNITURE.sofa_default.grid),
  };
  const defaultAnchor = (itemId: "board" | "calendar") => DEFAULT_LAYOUT.find((p) => p.itemId === itemId)!.anchor;

  it("보드·캘린더가 없으면 기본 자리에 더하고 서버 가구는 그대로 둔다", () => {
    const layout = withDefaultWallItems([sofaOnFloor]);

    expect(layout[0]).toEqual(sofaOnFloor);
    expect(layout.find((p) => p.itemId === "board")).toEqual({ itemId: "board", surface: "WALL_RIGHT", anchor: defaultAnchor("board") });
    expect(layout.find((p) => p.itemId === "calendar")?.anchor).toEqual(defaultAnchor("calendar"));
  });

  it("서버에 있는 벽 오브젝트는 서버 자리를 쓰고 중복해 더하지 않는다", () => {
    const serverBoard: Placement = { itemId: "board", userFurnitureId: 205, surface: "WALL_RIGHT", anchor: defaultAnchor("calendar") };
    const layout = withDefaultWallItems([sofaOnFloor, serverBoard]);

    expect(layout.filter((p) => p.itemId === "board")).toEqual([serverBoard]);
    // 캘린더 기본 자리를 서버 보드가 차지했으므로 캘린더는 다른 칸으로 비킨다
    expect(layout.find((p) => p.itemId === "calendar")?.anchor).not.toEqual(defaultAnchor("calendar"));
  });
});

describe("toPlacementRequest — 씬 배치를 저장 요청으로", () => {
  it("기본 4종의 좌표가 서버 신규 지급 좌표와 같고 자동 보정으로 움직이지 않는다", () => {
    const positions = {
      sofa_default: [198.125, 443.250], tv_default: [190.625, 334.688],
      dining_table_original: [64.604, 362.438], coffee_table_original: [127.417, 429.875],
    } as const;
    for (const [itemId, [positionX, positionY]] of Object.entries(positions)) {
      const placement = DEFAULT_LAYOUT.find((item) => item.itemId === itemId)!;
      expect(toPlacementRequest(placement)).toMatchObject({ positionX, positionY, placementDirection: "FRONT_RIGHT" });
      const [settled] = toPlacements([{ ...sofa, assetKey: itemId, positionX, positionY }]);
      expect(settled.anchor.x).toBeCloseTo(positionX, 3);
      expect(settled.anchor.y).toBeCloseTo(positionY, 3);
    }
  });

  it("면·방향·좌표를 채우고 좌표는 소수 3자리로 다듬는다", () => {
    const placement: Placement = { itemId: "sofa_default", userFurnitureId: 204, anchor: { x: 164.87512, y: 226 } };

    expect(toPlacementRequest(placement)).toEqual({
      placementStatus: "FLOOR",
      placementDirection: "FRONT_RIGHT",
      positionX: 164.875,
      positionY: 226,
      layer: 0,
    });
  });

  it("돌린 가구는 FRONT_LEFT, 벽에 걸린 것은 붙은 벽이 정한 방향을 보낸다", () => {
    expect(toPlacementRequest({ itemId: "bed_pink", anchor: { x: 100, y: 400 }, direction: "FRONT_LEFT" })).toMatchObject({
      placementDirection: "FRONT_LEFT",
    });
    expect(toPlacementRequest({ itemId: "window_sky_clouds", surface: "WALL_LEFT", anchor: { x: 60, y: 150 } })).toMatchObject({
      placementStatus: "LEFT_WALL",
      placementDirection: "FRONT_RIGHT",
    });
    expect(toPlacementRequest({ itemId: "board", surface: "WALL_RIGHT", anchor: { x: 240, y: 200 } })).toMatchObject({
      placementDirection: "FRONT_LEFT",
    });
  });

  it("씬 밖으로 나간 좌표는 경계로 당겨 400 을 피한다", () => {
    const request = toPlacementRequest({ itemId: "plant_monstera_terracotta", anchor: { x: -5, y: 700 } });

    expect(request).toMatchObject({ positionX: 0, positionY: 586 });
  });
});
