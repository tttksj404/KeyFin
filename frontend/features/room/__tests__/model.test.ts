import { FURNITURE } from "@/features/room/catalog";
import {
  canvasPointToScene,
  clamp,
  clampCamera,
  depthIndexAt,
  depthKey,
  getCanvasSize,
  getSceneScale,
  getSpriteRect,
  hitTestTopmost,
  isPointInPolygon,
  MAX_ZOOM,
  MIN_ZOOM,
  overflowsViewport,
  pickWaypoint,
  rectContainsPoint,
  rectsIntersect,
  SCENE_ASPECT_RATIO,
  SCENE_HEIGHT,
  SCENE_WIDTH,
  sceneRectToCanvas,
  segmentCrossesPolygon,
  sortByDepth,
  travelDurationMs,
  zoomAround,
} from "@/features/room/model";
import { CHARACTER_MOTION, DEFAULT_LAYOUT, FLOOR_POLYGON, getFootprintPolygon, getWalkBlockers, isFloorPlacement } from "@/features/room/scene";

describe("room scene 좌표계", () => {
  it("씬 단위는 세로 긴 방 그림과 같은 327×586 이다", () => {
    expect(SCENE_WIDTH).toBe(327);
    expect(SCENE_HEIGHT).toBe(586);
    expect(SCENE_ASPECT_RATIO).toBeCloseTo(327 / 586);
  });

  it("캔버스 폭에 따라 scale 과 높이를 구한다", () => {
    expect(getSceneScale(327)).toBe(1);
    expect(getSceneScale(654)).toBe(2);
    expect(getCanvasSize(654)).toEqual({ width: 654, height: 1172 });
  });

  it("발끝 기준점으로 스프라이트 사각형을 구한다", () => {
    const rect = getSpriteRect({ x: 160, y: 330 }, { width: 72, height: 106 });
    expect(rect.x).toBeCloseTo(124);
    expect(rect.y).toBeCloseTo(330 - 106 * 0.95);
    expect(rect.width).toBe(72);
    expect(rect.height).toBe(106);
  });

  it("기준점 비율을 바꾸면 좌상단 기준으로도 둘 수 있다", () => {
    const rect = getSpriteRect({ x: 10, y: 20 }, { width: 30, height: 40 }, { x: 0, y: 0 });
    expect(rect).toEqual({ x: 10, y: 20, width: 30, height: 40 });
  });

  it("씬 사각형을 scale 로 캔버스 픽셀로 바꾼다", () => {
    expect(sceneRectToCanvas({ x: 10, y: 20, width: 30, height: 40 }, 2)).toEqual({ x: 20, y: 40, width: 60, height: 80 });
  });

  it("clamp 는 범위를 벗어난 값을 경계로 자른다", () => {
    expect(clamp(-5, 0, 10)).toBe(0);
    expect(clamp(15, 0, 10)).toBe(10);
    expect(clamp(5, 0, 10)).toBe(5);
  });
});


describe("씬 카메라 (확대·이동)", () => {
  const canvas = getCanvasSize(327); // 327×586

  it("배율은 1~2 로, 평행이동은 방 밖 여백이 안 보이는 범위로 가둔다", () => {
    expect(clampCamera({ scale: 3, tx: 0, ty: 0 }, canvas).scale).toBe(MAX_ZOOM);
    expect(clampCamera({ scale: 0.5, tx: 0, ty: 0 }, canvas).scale).toBe(MIN_ZOOM);
    // 1배에서는 움직일 여지가 없다
    expect(clampCamera({ scale: 1, tx: 50, ty: -50 }, canvas)).toEqual({ scale: 1, tx: 0, ty: 0 });
    // 2배에서는 캔버스 한 장만큼(-327, -586) 까지만 밀 수 있다
    expect(clampCamera({ scale: 2, tx: 10, ty: 10 }, canvas)).toEqual({ scale: 2, tx: 0, ty: 0 });
    expect(clampCamera({ scale: 2, tx: -400, ty: -700 }, canvas)).toEqual({ scale: 2, tx: -327, ty: -586 });
    expect(clampCamera({ scale: 2, tx: -100, ty: -200 }, canvas)).toEqual({ scale: 2, tx: -100, ty: -200 });
  });

  it("캔버스가 화면보다 넓으면(홈 cover 맞춤) 1배에서도 넘치는 절반까지 좌우로 밀 수 있다", () => {
    const cover = getCanvasSize(419); // 419×751 — 390×750 화면을 채우는 폭
    const viewport = { width: 390, height: 750 };
    const half = (cover.width - viewport.width) / 2;

    expect(clampCamera({ scale: 1, tx: 0, ty: 0 }, cover, viewport)).toEqual({ scale: 1, tx: 0, ty: 0 });
    expect(clampCamera({ scale: 1, tx: 999, ty: 0 }, cover, viewport).tx).toBeCloseTo(half);
    expect(clampCamera({ scale: 1, tx: -999, ty: 0 }, cover, viewport).tx).toBeCloseTo(-half);
    // 세로는 딱 맞게 채워져 움직일 여지가 반올림 오차(1px 미만)뿐이다
    expect(Math.abs(clampCamera({ scale: 1, tx: 0, ty: 999 }, cover, viewport).ty)).toBeLessThan(1);
    expect(Math.abs(clampCamera({ scale: 1, tx: 0, ty: -999 }, cover, viewport).ty)).toBeLessThan(1);

    expect(overflowsViewport(cover, viewport)).toBe(true);
    // 캔버스가 화면에 딱 맞는 화면(방 꾸미기)은 전과 같이 1배에서 못 움직인다
    expect(overflowsViewport(canvas, canvas)).toBe(false);
    expect(clampCamera({ scale: 1, tx: 50, ty: -50 }, canvas, canvas)).toEqual({ scale: 1, tx: 0, ty: 0 });
  });

  it("핀치 중심으로 확대하면 그 점은 화면에서 제자리에 남는다", () => {
    const focal = { x: 200, y: 300 };
    const zoomed = zoomAround({ scale: 1, tx: 0, ty: 0 }, focal, 2);
    // 화면 좌표 = 씬점 * scale + t 이므로, 중심이 가리키던 씬점을 다시 그리면 같은 화면 좌표가 나온다
    expect(focal.x * zoomed.scale + zoomed.tx).toBeCloseTo(focal.x);
    expect(focal.y * zoomed.scale + zoomed.ty).toBeCloseTo(focal.y);
    expect(zoomed).toEqual({ scale: 2, tx: -200, ty: -300 });
  });

  it("이미 확대·이동한 상태에서 다시 확대해도 중심은 고정된다", () => {
    const from = { scale: 1.5, tx: -60, ty: -80 };
    const focal = { x: 120, y: 140 };
    const scenePoint = canvasPointToScene(focal, from, 1);
    const zoomed = zoomAround(from, focal, 2);
    expect(scenePoint.x * zoomed.scale + zoomed.tx).toBeCloseTo(focal.x);
    expect(scenePoint.y * zoomed.scale + zoomed.ty).toBeCloseTo(focal.y);
  });

  it("배율 상한을 넘겨 요청해도 2배에서 멈춘다", () => {
    expect(zoomAround({ scale: 2, tx: -327, ty: -404 }, { x: 0, y: 0 }, 4).scale).toBe(MAX_ZOOM);
  });

  it("터치 좌표는 카메라를 되돌려 씬 좌표가 된다", () => {
    // 1배·이동 없음이면 캔버스 scale 만 되돌린다
    expect(canvasPointToScene({ x: 327, y: 404 }, { scale: 1, tx: 0, ty: 0 }, 2)).toEqual({ x: 163.5, y: 202 });
    // 2배로 확대해 왼쪽 위로 민 상태
    expect(canvasPointToScene({ x: 100, y: 100 }, { scale: 2, tx: -100, ty: -200 }, 1)).toEqual({ x: 100, y: 150 });
  });

  it("씬 좌표를 그렸다가 되돌리면 원래 좌표가 나온다", () => {
    const camera = clampCamera({ scale: 1.8, tx: -120, ty: -240 }, canvas);
    const scenePoint = { x: 160, y: 330 };
    const sceneScale = getSceneScale(654);
    const canvasPoint = {
      x: scenePoint.x * sceneScale * camera.scale + camera.tx,
      y: scenePoint.y * sceneScale * camera.scale + camera.ty,
    };
    const back = canvasPointToScene(canvasPoint, camera, sceneScale);
    expect(back.x).toBeCloseTo(scenePoint.x);
    expect(back.y).toBeCloseTo(scenePoint.y);
  });
});
describe("깊이 정렬 (painter's algorithm)", () => {
  const a = { id: "a", anchor: { x: 0, y: 300 } };
  const b = { id: "b", anchor: { x: 0, y: 100 } };
  const c = { id: "c", anchor: { x: 0, y: 200 } };

  it("발끝 y 가 작은 것(뒤)부터 큰 것(앞) 순으로 정렬하고 입력은 바꾸지 않는다", () => {
    const input = [a, b, c];
    expect(sortByDepth(input).map((e) => e.id)).toEqual(["b", "c", "a"]);
    expect(input.map((e) => e.id)).toEqual(["a", "b", "c"]);
  });

  it("layer 가 큰 것은 y 와 무관하게 앞에 온다", () => {
    const rug = { id: "rug", anchor: { x: 0, y: 400 }, layer: -1 };
    const lamp = { id: "lamp", anchor: { x: 0, y: 50 }, layer: 1 };
    expect(sortByDepth([a, lamp, rug]).map((e) => e.id)).toEqual(["rug", "a", "lamp"]);
  });

  it("키가 같으면 입력 순서를 유지한다", () => {
    const first = { id: "first", anchor: { x: 0, y: 100 } };
    const second = { id: "second", anchor: { x: 5, y: 100 } };
    expect(sortByDepth([second, first]).map((e) => e.id)).toEqual(["second", "first"]);
  });

  it("depthIndexAt 은 정렬된 키 사이에서 캐릭터가 들어갈 위치를 준다", () => {
    const keys = sortByDepth([a, b, c]).map(depthKey); // y: 100, 200, 300
    expect(depthIndexAt(keys, 50)).toBe(0); // 전부 앞에 → 가장 먼저 그림
    expect(depthIndexAt(keys, 150)).toBe(1);
    expect(depthIndexAt(keys, 200)).toBe(2); // 같은 y 는 가구 뒤가 아니라 앞에 그린다
    expect(depthIndexAt(keys, 999)).toBe(3);
    expect(depthIndexAt(keys, 150, 1)).toBe(3); // layer 1 캐릭터는 항상 맨 앞
  });
});

describe("바닥 다각형", () => {
  it("바닥 안·밖을 판정한다", () => {
    expect(isPointInPolygon({ x: 160, y: 300 }, FLOOR_POLYGON)).toBe(true); // 방 가운데
    expect(isPointInPolygon({ x: 131, y: 60 }, FLOOR_POLYGON)).toBe(false); // 코너 위 벽
    expect(isPointInPolygon({ x: 10, y: 120 }, FLOOR_POLYGON)).toBe(false); // 왼쪽 벽
    expect(isPointInPolygon({ x: 320, y: 150 }, FLOOR_POLYGON)).toBe(false); // 오른쪽 벽
  });

  it("기본 배치의 가구 발끝은 모두 바닥 안에 있다", () => {
    for (const placement of DEFAULT_LAYOUT.filter(isFloorPlacement)) {
      expect(isPointInPolygon(placement.anchor, FLOOR_POLYGON)).toBe(true);
    }
  });

  it("카탈로그 크기는 PNG 비율을 유지한다", () => {
    // 크기는 배율(6.3px/씬 단위)로 줄인 값이라 PNG 종횡비를 검사한다(sofa_original/left.png 830x707).
    const sofa = FURNITURE.sofa_default.views.FRONT_RIGHT.size;
    const fridge = FURNITURE.fridge_default.views.FRONT_RIGHT.size;
    const plant = FURNITURE.plant_monstera_terracotta.views.FRONT_RIGHT.size;
    expect(sofa.height / sofa.width).toBeCloseTo(707 / 830, 2);
    expect(fridge.height).toBeGreaterThan(fridge.width);
    expect(plant.height).toBeGreaterThan(plant.width);
  });
});

describe("캐릭터 이동 (웨이포인트)", () => {
  /** 0~1 수열을 순서대로 돌려주는 고정 난수 */
  const sequence = (values: number[]) => {
    let i = 0;
    return () => values[i++ % values.length];
  };
  const blocked = getWalkBlockers(DEFAULT_LAYOUT);

  it("선분이 다각형을 지나는지 근사로 판정한다", () => {
    const square = [
      { x: 100, y: 100 },
      { x: 150, y: 100 },
      { x: 150, y: 150 },
      { x: 100, y: 150 },
    ];
    expect(segmentCrossesPolygon({ x: 0, y: 125 }, { x: 300, y: 125 }, square)).toBe(true);
    expect(segmentCrossesPolygon({ x: 0, y: 0 }, { x: 300, y: 0 }, square)).toBe(false);
    expect(rectContainsPoint({ x: 100, y: 100, width: 50, height: 50 }, { x: 120, y: 120 })).toBe(true);
    expect(rectContainsPoint({ x: 100, y: 100, width: 50, height: 50 }, { x: 99, y: 120 })).toBe(false);
  });

  it("가구 발자국은 발끝을 앞쪽 경계로 두고 뒤로 뻗는다", () => {
    const sofa = DEFAULT_LAYOUT.find((p) => p.itemId === "sofa_default")!;
    const polygon = getFootprintPolygon(sofa);
    const xs = polygon.map((p) => p.x);
    const ys = polygon.map((p) => p.y);
    expect(Math.min(...ys)).toBeLessThan(sofa.anchor.y);
    expect(Math.max(...ys)).toBeGreaterThanOrEqual(sofa.anchor.y);
    expect(Math.min(...xs)).toBeLessThanOrEqual(sofa.anchor.x);
    expect(Math.max(...xs)).toBeGreaterThanOrEqual(sofa.anchor.x);
  });

  it("고른 목적지는 항상 바닥 안·가구 발자국 밖·벽 마진 밖이고 최소 거리를 넘는다", () => {
    let found = 0;
    let from = CHARACTER_MOTION.start;
    for (let i = 0; i < 100; i++) {
      const target = pickWaypoint({ from, polygon: FLOOR_POLYGON, blocked, xInset: 42 });
      if (!target) continue;
      found++;
      expect(target.x).toBeGreaterThanOrEqual(42);
      expect(target.x).toBeLessThanOrEqual(327 - 42);
      expect(isPointInPolygon(target, FLOOR_POLYGON)).toBe(true);
      expect(isPointInPolygon({ x: target.x, y: target.y - 12 }, FLOOR_POLYGON)).toBe(true);
      expect(blocked.some((area) => isPointInPolygon(target, area))).toBe(false);
      expect(blocked.some((area) => segmentCrossesPolygon(from, target, area))).toBe(false);
      expect(Math.hypot(target.x - from.x, target.y - from.y)).toBeGreaterThanOrEqual(40);
      from = target;
    }
    expect(found).toBeGreaterThan(60);
  });

  it("후보가 전부 벽 마진 안이거나 바닥 밖이면 null 을 돌려준다", () => {
    // (0.4, 0.02) → 코너 바로 아래 점: 바닥 안이지만 12 위쪽이 벽이라 거른다
    const cornerOnly = sequence([0.4, 0.02]);
    expect(pickWaypoint({ from: { x: 300, y: 380 }, polygon: FLOOR_POLYGON, blocked, rng: cornerOnly, maxTries: 6 })).toBeNull();
    // 0 → 경계 상자의 좌상단(0,112) 은 왼쪽 벽 위
    expect(pickWaypoint({ from: { x: 0, y: 0 }, polygon: FLOOR_POLYGON, blocked, rng: () => 0, maxTries: 5 })).toBeNull();
  });

  it("이동 시간은 거리 ÷ 속도다", () => {
    expect(travelDurationMs({ x: 0, y: 0 }, { x: 42, y: 0 }, 42)).toBe(1000);
    expect(travelDurationMs({ x: 0, y: 0 }, { x: 0, y: 0 }, 42)).toBe(0);
  });
});

// 배치 유효성·드래그는 격자 기준으로 옮겼다. grid.test.ts 를 본다.
describe("가구 편집 (히트 테스트)", () => {
  it("사각형 겹침을 판정한다", () => {
    expect(rectsIntersect({ x: 0, y: 0, width: 10, height: 10 }, { x: 5, y: 5, width: 10, height: 10 })).toBe(true);
    expect(rectsIntersect({ x: 0, y: 0, width: 10, height: 10 }, { x: 10, y: 0, width: 10, height: 10 })).toBe(false);
  });

  it("히트 테스트는 그리는 순서상 가장 앞의 것을 고른다", () => {
    const targets = [
      { id: "back", rect: { x: 0, y: 0, width: 100, height: 100 } },
      { id: "front", rect: { x: 50, y: 50, width: 100, height: 100 } },
    ];
    expect(hitTestTopmost({ x: 75, y: 75 }, targets)).toBe("front");
    expect(hitTestTopmost({ x: 10, y: 10 }, targets)).toBe("back");
    expect(hitTestTopmost({ x: 300, y: 300 }, targets)).toBeNull();
  });
});
