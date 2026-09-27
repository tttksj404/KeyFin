import { WALL_ITEMS, isWallItemId } from "@/features/room/catalog";
import { anchorToCell, cellsOverlap, fitsOnSurface } from "@/features/room/grid";
import { SCENE_HEIGHT, SCENE_WIDTH, popoverBelow } from "@/features/room/model";
import { DEFAULT_LAYOUT, DEFAULT_WALL_CELLS, SURFACES, getWallItemRect, isFloorPlacement, isPlaceableOnWall } from "@/features/room/scene";

/** 씬 사각형이 씬 안에 온전히 들어가는지 */
const insideScene = (rect: { x: number; y: number; width: number; height: number }) =>
  rect.x >= 0 && rect.y >= 0 && rect.x + rect.width <= SCENE_WIDTH && rect.y + rect.height <= SCENE_HEIGHT;

describe("벽 오브젝트 기본 배치", () => {
  it("보드·캘린더는 오른쪽 벽에 있고 가구 배치와 섞여 한 배열에 들어간다", () => {
    const wall = DEFAULT_LAYOUT.filter((p) => !isFloorPlacement(p));
    expect(wall.map((p) => [p.itemId, p.surface])).toEqual([
      ["calendar", "WALL_RIGHT"],
      ["board", "WALL_RIGHT"],
    ]);
    expect(DEFAULT_LAYOUT.filter(isFloorPlacement).every((p) => !isWallItemId(p.itemId))).toBe(true);
  });

  it("기본 자리는 자기 벽 칸에 들어가고 씬 안에 보인다", () => {
    for (const { itemId, cell } of DEFAULT_WALL_CELLS) {
      const item = WALL_ITEMS[itemId];
      expect(fitsOnSurface(SURFACES[item.surface], cell, item.grid)).toBe(true);
      expect(isPlaceableOnWall(item.surface, cell, item.grid)).toBe(true);
    }
  });

  it("스프라이트 사각형은 오른쪽 벽 위쪽에 나란히 놓이고 겹치지 않으며 씬 안에 있다", () => {
    const board = getWallItemRect(DEFAULT_LAYOUT, "board")!;
    const calendar = getWallItemRect(DEFAULT_LAYOUT, "calendar")!;

    expect(insideScene(board)).toBe(true);
    expect(insideScene(calendar)).toBe(true);
    // 캘린더가 코너(x 164) 쪽, 보드가 그 오른쪽 (2026-09-20: 끝 칸은 홈에서 오른쪽이 잘려 캘린더를 안쪽으로 옮겼다).
    expect(calendar.x).toBeGreaterThanOrEqual(164);
    expect(calendar.x + calendar.width).toBeLessThanOrEqual(board.x);
    expect(board.y + board.height).toBeLessThan(371);
    expect(calendar.y + calendar.height).toBeLessThan(371);
  });

  it("배치에 없는 벽 오브젝트는 사각형이 없다", () => {
    expect(getWallItemRect(DEFAULT_LAYOUT.filter(isFloorPlacement), "board")).toBeNull();
  });
});

describe("isPlaceableOnWall", () => {
  const board = WALL_ITEMS.board;

  it("벽걸이는 1×1 칸(반 칸 단위 2×2)이다", () => {
    expect(board.grid).toEqual({ w: 2, d: 2 });
    expect(WALL_ITEMS.calendar.grid).toEqual({ w: 2, d: 2 });
  });

  it("새 방은 벽 격자가 전부 화면 안이라 아홉 칸 모두 놓을 수 있다 (2026-09-18)", () => {
    for (const col of [0, 2, 4]) {
      for (const row of [0, 2, 4]) {
        expect(isPlaceableOnWall("WALL_RIGHT", { col, row }, board.grid)).toBe(true);
        expect(isPlaceableOnWall("WALL_LEFT", { col, row }, board.grid)).toBe(true);
      }
    }
  });

  it("벽 밖으로 나가는 칸은 놓을 수 없다", () => {
    expect(isPlaceableOnWall("WALL_RIGHT", { col: 8, row: 2 }, board.grid)).toBe(false);
    expect(isPlaceableOnWall("WALL_RIGHT", { col: 0, row: 8 }, board.grid)).toBe(false);
  });

  it("스냅한 칸을 다시 기준점으로 되돌리면 같은 칸이다(드래그 왕복)", () => {
    const calendar = WALL_ITEMS.calendar;
    const placed = DEFAULT_LAYOUT.find((p) => p.itemId === "calendar")!;
    expect(anchorToCell(SURFACES.WALL_RIGHT, placed.anchor, calendar.grid)).toEqual({ col: 0, row: 4 });
  });

  it("같은 벽에서 칸을 나눠 가지면 겹친다", () => {
    expect(cellsOverlap({ col: 2, row: 2 }, board.grid, { col: 3, row: 3 }, board.grid)).toBe(true);
    expect(cellsOverlap({ col: 2, row: 2 }, board.grid, { col: 4, row: 2 }, board.grid)).toBe(false);
  });
});

describe("popoverBelow", () => {
  it("오브젝트 아래에 붙이고 씬 폭 안에 가둔다", () => {
    expect(popoverBelow({ x: 20, y: 30, width: 90, height: 60 }, 250)).toEqual({ x: 20, y: 98 });
    expect(popoverBelow({ x: 242, y: 26, width: 64, height: 80 }, 250)).toEqual({ x: SCENE_WIDTH - 250, y: 114 });
  });
});
