import { FURNITURE } from "@/features/room/catalog";
import {
  anchorToCell,
  cellAnchor,
  cellDepth,
  cellsOverlap,
  cellToScene,
  fitsOnSurface,
  halfSpan,
  isGridPlacementValid,
  isOnSurface,
  sceneToCell,
  snapToCell,
  type GridFootprint,
  type GridPlacement,
  type SurfaceDef,
} from "@/features/room/grid";
import { DEFAULT_CELLS, DEFAULT_LAYOUT, SURFACES, isFloorPlacement, isPlaceableOnFloor } from "@/features/room/scene";

const FLOOR = SURFACES.FLOOR;

/** 화면상 두 점 사이 거리 */
const dist = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y);

describe("격자 ↔ 씬 좌표 변환", () => {
  it("네 꼭짓점이 격자의 네 모서리로 간다", () => {
    const { cols, rows } = halfSpan(FLOOR);
    const corners: [number, number][] = [
      [0, 0],
      [cols, 0],
      [cols, rows],
      [0, rows],
    ];
    corners.forEach(([col, row], index) => {
      const point = cellToScene(FLOOR, { col, row });
      expect(point.x).toBeCloseTo(FLOOR.quad[index].x, 6);
      expect(point.y).toBeCloseTo(FLOOR.quad[index].y, 6);
    });
  });

  it("칸 → 씬 → 칸 왕복이 원래 값을 준다", () => {
    for (const cell of [
      { col: 0, row: 0 },
      { col: 3, row: 11 },
      { col: 9, row: 4 },
      { col: 15, row: 15 },
    ]) {
      const back = sceneToCell(FLOOR, cellToScene(FLOOR, cell));
      expect(back.col).toBeCloseTo(cell.col, 6);
      expect(back.row).toBeCloseTo(cell.row, 6);
    }
  });

  it("반 칸이 아닌 위치도 변환한다(드래그 중 미리보기)", () => {
    const point = cellToScene(FLOOR, { col: 4.5, row: 7.25 });
    const back = sceneToCell(FLOOR, point);
    expect(back.col).toBeCloseTo(4.5, 6);
    expect(back.row).toBeCloseTo(7.25, 6);
  });

  it("칸 크기가 격자 전체에서 같다", () => {
    // 방 그림에 원근이 거의 없어 면을 평행사변형으로 잡았다. 뒤쪽이 작아지면 그림과 어긋난다.
    const cellWidth = (col: number, row: number) => dist(cellToScene(FLOOR, { col, row }), cellToScene(FLOOR, { col: col + 2, row }));
    const cellDepthOf = (col: number, row: number) => dist(cellToScene(FLOOR, { col, row }), cellToScene(FLOOR, { col, row: row + 2 }));
    expect(cellWidth(0, 0)).toBeCloseTo(cellWidth(12, 14), 6);
    expect(cellDepthOf(0, 0)).toBeCloseTo(cellDepthOf(14, 12), 6);
  });

  it("면 안팎을 판정한다", () => {
    expect(isOnSurface(FLOOR, cellToScene(FLOOR, { col: 8, row: 8 }))).toBe(true);
    // 뒤 코너보다 위 = 벽 쪽
    expect(isOnSurface(FLOOR, { x: 164, y: 120 })).toBe(false);
  });
});

describe("스냅과 배치 검증", () => {
  const sofa: GridFootprint = { w: 8, d: 4 };

  it("스냅은 반 칸 단위 정수를 준다", () => {
    const near = cellToScene(FLOOR, { col: 5.4, row: 9.6 });
    expect(snapToCell(FLOOR, near, { w: 2, d: 2 })).toEqual({ col: 5, row: 10 });
  });

  it("발자국이 면 밖으로 나가지 않게 가둔다", () => {
    const { cols, rows } = halfSpan(FLOOR);
    const farCorner = cellToScene(FLOOR, { col: cols, row: rows });
    expect(snapToCell(FLOOR, farCorner, sofa)).toEqual({ col: cols - sofa.w, row: rows - sofa.d });
  });

  it("면을 벗어난 점도 안쪽으로 가둔다", () => {
    expect(snapToCell(FLOOR, { x: -500, y: -500 }, sofa)).toEqual({ col: 0, row: 0 });
  });

  it("발자국이 온전히 들어가야 유효하다", () => {
    expect(fitsOnSurface(FLOOR, { col: 16, row: 12 }, sofa)).toBe(true);
    expect(fitsOnSurface(FLOOR, { col: 17, row: 12 }, sofa)).toBe(false); // 17 + 8 > 24
    expect(fitsOnSurface(FLOOR, { col: -1, row: 0 }, sofa)).toBe(false);
    expect(fitsOnSurface(FLOOR, { col: 0.5, row: 0 }, sofa)).toBe(false); // 정수만 허용
  });

  it("겹침은 반 칸 사각형 비교로 판정한다", () => {
    const table: GridFootprint = { w: 4, d: 4 };
    expect(cellsOverlap({ col: 0, row: 0 }, sofa, { col: 7, row: 2 }, table)).toBe(true);
    // 소파는 col 0~7 을 쓰므로 8부터는 닿지 않는다
    expect(cellsOverlap({ col: 0, row: 0 }, sofa, { col: 8, row: 2 }, table)).toBe(false);
    expect(cellsOverlap({ col: 0, row: 0 }, sofa, { col: 0, row: 4 }, table)).toBe(false);
  });

  it("깊이 키는 앞쪽 배치가 크다", () => {
    const back = cellDepth({ col: 0, row: 0 }, sofa);
    const front = cellDepth({ col: 8, row: 12 }, sofa);
    expect(front).toBeGreaterThan(back);
  });
});

describe("배치 가능 판정", () => {
  const sofa: GridFootprint = { w: 2, d: 6 };
  const small: GridFootprint = { w: 2, d: 2 };

  it("빈 자리는 놓을 수 있다", () => {
    expect(isGridPlacementValid(FLOOR, { col: 4, row: 4 }, sofa, [])).toBe(true);
  });

  it("다른 가구와 칸을 나눠 가지면 놓을 수 없다", () => {
    const others: GridPlacement[] = [{ cell: { col: 4, row: 6 }, footprint: small }];
    expect(isGridPlacementValid(FLOOR, { col: 4, row: 4 }, sofa, others)).toBe(false);
    // 한 칸만 비켜서면 닿지 않는다
    expect(isGridPlacementValid(FLOOR, { col: 6, row: 4 }, sofa, others)).toBe(true);
  });

  it("보이는 바닥 밖이면 놓을 수 없다", () => {
    expect(isGridPlacementValid(FLOOR, { col: 14, row: 0 }, small, [], (cell) => isPlaceableOnFloor(cell, small))).toBe(false);
  });
});

describe("세 면의 격자 정의", () => {
  it("바닥은 12 × 12, 두 벽은 각각 3 × 4 이다(줄 없는 세로 긴 방, 2026-09-18)", () => {
    expect([SURFACES.FLOOR.cols, SURFACES.FLOOR.rows]).toEqual([12, 12]);
    expect([SURFACES.WALL_LEFT.cols, SURFACES.WALL_LEFT.rows]).toEqual([3, 4]);
    expect([SURFACES.WALL_RIGHT.cols, SURFACES.WALL_RIGHT.rows]).toEqual([3, 4]);
  });

  it("두 벽의 평균 칸 폭 차이가 10% 안이다", () => {
    // 새 방은 코너가 정중앙이라 좌우 벽 폭이 164·163 으로 같다. 그래서 칸 수도 3 으로 같다.
    const averageCellWidth = (surface: SurfaceDef) => {
      const span = halfSpan(surface);
      return dist(cellToScene(surface, { col: 0, row: 0 }), cellToScene(surface, { col: span.cols, row: 0 })) / surface.cols;
    };
    const left = averageCellWidth(SURFACES.WALL_LEFT);
    const right = averageCellWidth(SURFACES.WALL_RIGHT);
    expect(Math.abs(left - right) / right).toBeLessThan(0.1);
  });

  it("벽도 칸 크기가 균일하다", () => {
    const wall = SURFACES.WALL_LEFT;
    const span = halfSpan(wall);
    const nearEdge = dist(cellToScene(wall, { col: 0, row: 0 }), cellToScene(wall, { col: 2, row: 0 }));
    const nearCorner = dist(cellToScene(wall, { col: span.cols - 2, row: 0 }), cellToScene(wall, { col: span.cols, row: 0 }));
    expect(nearEdge).toBeCloseTo(nearCorner, 6);
  });

  it("두 벽은 코너 (164, 286) 을 공유한다", () => {
    const leftCorner = cellToScene(SURFACES.WALL_LEFT, { col: 6, row: 8 });
    const rightCorner = cellToScene(SURFACES.WALL_RIGHT, { col: 0, row: 8 });
    expect(leftCorner.x).toBeCloseTo(rightCorner.x, 6);
    expect(leftCorner.y).toBeCloseTo(rightCorner.y, 6);
    expect(leftCorner.x).toBeCloseTo(164, 6);
    expect(leftCorner.y).toBeCloseTo(286, 6);
  });

  it("기본 배치의 가구 발끝은 모두 바닥 면 안에 있다", () => {
    for (const placed of DEFAULT_LAYOUT.filter(isFloorPlacement)) {
      expect(isOnSurface(SURFACES.FLOOR, placed.anchor)).toBe(true);
    }
  });

  it("기본 배치는 칸이 겹치지 않고 모두 바닥 안에 들어간다", () => {
    const placements: GridPlacement[] = DEFAULT_CELLS.map(({ itemId, cell }) => ({ cell, footprint: FURNITURE[itemId].grid }));
    placements.forEach((placement, index) => {
      const others = placements.filter((_, other) => other !== index);
      expect(isGridPlacementValid(FLOOR, placement.cell, placement.footprint, others)).toBe(true);
    });
  });

  it("기본 배치는 모두 보이는 바닥 안에 놓인다", () => {
    // 격자가 화면 밖까지 뻗으므로 칸에 들어가는 것만으로는 부족하다.
    for (const { itemId, cell } of DEFAULT_CELLS) {
      expect(isPlaceableOnFloor(cell, FURNITURE[itemId].grid)).toBe(true);
    }
  });

  it("화면 밖 칸은 놓을 수 없다", () => {
    expect(isPlaceableOnFloor({ col: 14, row: 0 }, FURNITURE.plant_monstera_terracotta.grid)).toBe(false);
  });

  it("발끝을 칸으로 되돌리면 원래 칸이 나온다", () => {
    for (const { itemId, cell } of DEFAULT_CELLS) {
      const footprint = FURNITURE[itemId].grid;
      expect(anchorToCell(FLOOR, cellAnchor(FLOOR, cell, footprint), footprint)).toEqual(cell);
    }
  });
});
