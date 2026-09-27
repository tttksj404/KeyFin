import { isPointInPolygon, type ScenePoint } from "@/features/room/model";
import { DEFAULT_LAYOUT, FLOOR_POLYGON, getFootprintPolygon, getSeatPoint, type Placement } from "@/features/room/scene";

/** 앉을 자리가 나와야 하는 배치에서만 쓴다 — null 이면 그 자체가 실패다 */
function seatOf(placements: readonly Placement[]): ScenePoint {
  const seat = getSeatPoint(placements);
  if (seat === null) throw new Error("소파가 있는 배치인데 앉을 자리가 null 이다");
  return seat;
}

function sofaAnchor(placements: readonly Placement[]): ScenePoint {
  const sofa = placements.find((placement) => placement.itemId === "sofa_default");
  if (sofa === undefined) throw new Error("배치에 소파가 없다");
  return sofa.anchor;
}

function withSofaAt(anchor: ScenePoint): Placement[] {
  return DEFAULT_LAYOUT.map((placement) => (placement.itemId === "sofa_default" ? { ...placement, anchor } : placement));
}

describe("소파에 앉을 자리", () => {
  it("기본 배치의 소파 가로 한가운데, 바닥 안에 있다", () => {
    const seat = seatOf(DEFAULT_LAYOUT);

    expect(isPointInPolygon(seat, FLOOR_POLYGON)).toBe(true);
    expect(seat.x).toBe(sofaAnchor(DEFAULT_LAYOUT).x);
  });

  it("발끝이 소파 발자국보다 앞이라 깊이 정렬에서 소파에 가려지지 않는다", () => {
    const footprint = getFootprintPolygon({ itemId: "sofa_default", anchor: sofaAnchor(DEFAULT_LAYOUT) });
    const frontY = Math.max(...footprint.map((corner) => corner.y));

    expect(seatOf(DEFAULT_LAYOUT).y).toBeGreaterThan(frontY);
  });

  it("소파를 옮기면 앉을 자리도 따라간다", () => {
    const seat = seatOf(withSofaAt({ x: 120, y: 470 }));

    expect(seat.x).toBe(120);
    expect(seat.y).toBeGreaterThan(470);
  });

  it("소파가 없으면 앉을 자리도 없다 — 그때는 걷기만 한다", () => {
    expect(getSeatPoint(DEFAULT_LAYOUT.filter((placement) => placement.itemId !== "sofa_default"))).toBeNull();
    expect(getSeatPoint([])).toBeNull();
  });

  it("소파가 바닥 맨 앞에 붙어 앉을 자리가 바닥 밖이면 앉지 않는다", () => {
    expect(getSeatPoint(withSofaAt({ x: 164, y: 586 }))).toBeNull();
  });
});
