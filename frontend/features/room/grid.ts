import type { ScenePoint } from "@/features/room/model";

/**
 * 격자 좌표계. 방의 각 면(바닥·왼쪽 벽·오른쪽 벽)에 칸을 얹고 칸 번호 ↔ 씬 좌표를 오간다.
 *
 * 면은 화면에서 직사각형이 아니므로 단위 정사각형 → 그 사각형의 사영변환(호모그래피)으로 매핑한다.
 * 지금 방 그림은 원근이 거의 없어 네 꼭짓점을 평행사변형으로 잡았고(scene.ts SURFACES),
 * 그 경우 변환은 아핀으로 떨어져 칸 크기가 어디서나 같다. 원근이 있는 그림으로 바꿔도 이 코드는 그대로 쓴다.
 *
 * 저장 단위는 "반 칸"이다. 가구가 칸에 반씩 걸치게 두려고 소수점을 쓰는 대신 단위를 반으로 줄였다.
 * 그래서 col·row 는 항상 정수이고, 8칸짜리 축의 범위는 0~15 이다.
 */

/** 한 칸에 들어가는 반 칸 수 */
export const HALF_PER_CELL = 2;

/**
 * 사영변환 행렬(행 우선 3×3). [x·w, y·w, w] = M · [u, v, 1] 을 뜻한다.
 * 역변환도 같은 모양이라 project() 하나로 양방향을 처리한다.
 */
export type Projection = readonly [number, number, number, number, number, number, number, number, number];

/**
 * 면의 네 꼭짓점. 순서는 (col 0, row 0) → (col 끝, row 0) → (col 끝, row 끝) → (col 0, row 끝) 이다.
 * 순서를 어기면 격자가 뒤집히거나 꼬인다.
 */
export type SurfaceQuad = readonly [ScenePoint, ScenePoint, ScenePoint, ScenePoint];

export type SurfaceDef = {
  quad: SurfaceQuad;
  /** 칸 수(반 칸 아님). 저장 좌표의 범위는 0 ~ cols·2 - 1 */
  cols: number;
  rows: number;
};

/** 반 칸 단위 격자 좌표. 짝수면 칸에 딱 맞고 홀수면 반 칸 걸친다. */
export type GridCell = { col: number; row: number };

/** 가구가 차지하는 칸 수(반 칸 단위). 소파는 { w: 6, d: 2 } = 3칸 × 1칸 */
export type GridFootprint = { w: number; d: number };

/** 축별 반 칸 개수 */
export function halfSpan(surface: SurfaceDef): { cols: number; rows: number } {
  return { cols: surface.cols * HALF_PER_CELL, rows: surface.rows * HALF_PER_CELL };
}

/**
 * 단위 정사각형 (0,0)-(1,0)-(1,1)-(0,1) 을 quad 로 보내는 사영변환.
 * 네 점이 평행사변형이면 g·h 가 0 이 되어 자연스럽게 아핀 변환으로 떨어진다.
 */
export function projectionFromQuad(quad: SurfaceQuad): Projection {
  const [p0, p1, p2, p3] = quad;
  const sx = p0.x - p1.x + p2.x - p3.x;
  const sy = p0.y - p1.y + p2.y - p3.y;

  const dx1 = p1.x - p2.x;
  const dx2 = p3.x - p2.x;
  const dy1 = p1.y - p2.y;
  const dy2 = p3.y - p2.y;

  const den = dx1 * dy2 - dx2 * dy1;
  if (den === 0) throw new Error("격자 사각형이 축퇴했다(세 점이 한 직선 위에 있다)");

  const g = (sx * dy2 - dx2 * sy) / den;
  const h = (dx1 * sy - sx * dy1) / den;

  return [
    p1.x - p0.x + g * p1.x,
    p3.x - p0.x + h * p3.x,
    p0.x,
    p1.y - p0.y + g * p1.y,
    p3.y - p0.y + h * p3.y,
    p0.y,
    g,
    h,
    1,
  ];
}

/** 사영변환을 한 점에 적용한다. 역행렬을 넣으면 반대 방향이 된다. */
export function project(m: Projection, u: number, v: number): ScenePoint {
  const w = m[6] * u + m[7] * v + m[8];
  return { x: (m[0] * u + m[1] * v + m[2]) / w, y: (m[3] * u + m[4] * v + m[5]) / w };
}

/** 동차 좌표의 w. 0 이하면 지평선 뒤라 나눗셈 결과의 부호가 뒤집힌다. */
function homogeneousW(m: Projection, u: number, v: number): number {
  return m[6] * u + m[7] * v + m[8];
}

/** 여인수 전개로 구한 역행렬. 스케일은 project() 의 나눗셈이 흡수하므로 정규화하지 않는다. */
export function invert(m: Projection): Projection {
  const [a, b, c, d, e, f, g, h, i] = m;
  const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
  if (det === 0) throw new Error("사영변환을 되돌릴 수 없다");
  return [
    e * i - f * h,
    c * h - b * i,
    b * f - c * e,
    f * g - d * i,
    a * i - c * g,
    c * d - a * f,
    d * h - e * g,
    b * g - a * h,
    a * e - b * d,
  ];
}

/** 반 칸 좌표 → 씬 좌표. 정수가 아니어도 되므로 드래그 중 미리보기에도 쓴다. */
export function cellToScene(surface: SurfaceDef, cell: GridCell): ScenePoint {
  const span = halfSpan(surface);
  return project(projectionFromQuad(surface.quad), cell.col / span.cols, cell.row / span.rows);
}

/**
 * 씬 좌표 → 반 칸 좌표(실수). 면 밖이면 0~span 범위를 벗어난 값이 나온다.
 *
 * 지평선 뒤(면을 화면 위로 한참 벗어난 곳)의 점은 사영 역변환에서 w 가 음수가 되어
 * 부호가 뒤집힌 큰 값이 나온다. 그대로 두면 "뒤쪽 밖"이 "앞쪽 끝"으로 둔갑하므로 -Infinity 로 돌려
 * 뒤쪽 밖임을 분명히 한다. 가두면(snapToCell) 뒤 모서리로 붙는다.
 */
export function sceneToCell(surface: SurfaceDef, point: ScenePoint): GridCell {
  const span = halfSpan(surface);
  const inverse = invert(projectionFromQuad(surface.quad));
  if (homogeneousW(inverse, point.x, point.y) <= 0) return { col: -Infinity, row: -Infinity };
  const uv = project(inverse, point.x, point.y);
  return { col: uv.x * span.cols, row: uv.y * span.rows };
}

/** 면 안에 있는지. 경계 위의 점은 안으로 친다. */
export function isOnSurface(surface: SurfaceDef, point: ScenePoint): boolean {
  const span = halfSpan(surface);
  const cell = sceneToCell(surface, point);
  return cell.col >= 0 && cell.col <= span.cols && cell.row >= 0 && cell.row <= span.rows;
}

function clamp(value: number, min: number, max: number): number {
  const clamped = value < min ? min : value > max ? max : value;
  // Math.round 는 -0.4 를 -0 으로 만든다. 그대로 두면 서버로 나가는 값과 비교가 어긋나므로 0 으로 맞춘다.
  return clamped === 0 ? 0 : clamped;
}

/**
 * 씬 좌표를 놓을 수 있는 반 칸 자리로 스냅한다.
 * 발자국이 면 밖으로 나가지 않도록 좌상단 기준으로 가둔다.
 */
export function snapToCell(surface: SurfaceDef, point: ScenePoint, footprint: GridFootprint): GridCell {
  const span = halfSpan(surface);
  const raw = sceneToCell(surface, point);
  return {
    col: clamp(Math.round(raw.col), 0, Math.max(0, span.cols - footprint.w)),
    row: clamp(Math.round(raw.row), 0, Math.max(0, span.rows - footprint.d)),
  };
}

/** 발자국이 면 안에 온전히 들어가는지 */
export function fitsOnSurface(surface: SurfaceDef, cell: GridCell, footprint: GridFootprint): boolean {
  const span = halfSpan(surface);
  return (
    Number.isInteger(cell.col) &&
    Number.isInteger(cell.row) &&
    cell.col >= 0 &&
    cell.row >= 0 &&
    cell.col + footprint.w <= span.cols &&
    cell.row + footprint.d <= span.rows
  );
}

/** 두 배치가 칸을 나눠 갖는지. 반 칸 단위 정수 비교라 근사가 없다. */
export function cellsOverlap(a: GridCell, af: GridFootprint, b: GridCell, bf: GridFootprint): boolean {
  return (
    a.col < b.col + bf.w && b.col < a.col + af.w && a.row < b.row + bf.d && b.row < a.row + af.d
  );
}

/**
 * 깊이 정렬 키. 두 축 모두 시청자 쪽으로 증가하므로 합이 크면 앞이다.
 * 화면 y 로 정렬하던 기존 방식과 달리 면이 기울어도 순서가 틀리지 않는다.
 */
export function cellDepth(cell: GridCell, footprint: GridFootprint): number {
  return cell.col + footprint.w / 2 + (cell.row + footprint.d / 2);
}

/**
 * 칸의 무게중심. 스프라이트는 자기 접지면의 무게중심을 이 점에 맞춰 그린다(catalog 의 anchor).
 *
 * 두 격자 축이 모두 화면 아래로 기울어 "앞쪽 변"이 하나로 정해지지 않는다. 어느 한 변이나
 * 꼭짓점에 맞추면 발자국보다 작은 가구가 칸 모서리에 걸쳐 보인다. 무게중심끼리 맞추면
 * 발자국을 꽉 채우는 가구는 칸과 겹쳐 놓이고(격자가 가구 바로 밑) 작은 가구는 칸 한가운데에 선다.
 */
export function cellAnchor(surface: SurfaceDef, cell: GridCell, footprint: GridFootprint): ScenePoint {
  return cellToScene(surface, { col: cell.col + footprint.w / 2, row: cell.row + footprint.d / 2 });
}

/** cellAnchor 의 역. 발끝 좌표를 발자국의 뒤 모서리 칸으로 되돌린다(면 안으로 가둔다). */
export function anchorToCell(surface: SurfaceDef, anchor: ScenePoint, footprint: GridFootprint): GridCell {
  const span = halfSpan(surface);
  const raw = sceneToCell(surface, anchor);
  return {
    col: clamp(Math.round(raw.col - footprint.w / 2), 0, Math.max(0, span.cols - footprint.w)),
    row: clamp(Math.round(raw.row - footprint.d / 2), 0, Math.max(0, span.rows - footprint.d)),
  };
}

/** 발자국의 네 꼭짓점(씬 좌표). 면이 평행사변형이라 발자국도 평행사변형이다. */
export function cellCorners(surface: SurfaceDef, cell: GridCell, footprint: GridFootprint): ScenePoint[] {
  return [
    { col: cell.col, row: cell.row },
    { col: cell.col + footprint.w, row: cell.row },
    { col: cell.col + footprint.w, row: cell.row + footprint.d },
    { col: cell.col, row: cell.row + footprint.d },
  ].map((corner) => cellToScene(surface, corner));
}

/**
 * 발자국 윤곽을 발끝 기준 상대 좌표로 준다. 면이 평행사변형이라 어느 칸에 놓든 모양이 같으므로
 * 한 번 만들어 두고 발끝 위치로 옮겨 그리면 된다(드래그 중 매 프레임 다시 만들지 않아도 된다).
 */
export function footprintOutline(surface: SurfaceDef, footprint: GridFootprint): ScenePoint[] {
  const origin: GridCell = { col: 0, row: 0 };
  const anchor = cellAnchor(surface, origin, footprint);
  return cellCorners(surface, origin, footprint).map((corner) => ({ x: corner.x - anchor.x, y: corner.y - anchor.y }));
}

/** 면 위의 한 배치. 겹침 검사에 쓴다. */
export type GridPlacement = { cell: GridCell; footprint: GridFootprint };

/**
 * 놓을 수 있는 자리인지: 면 안에 온전히 들어가고 다른 배치와 칸을 나눠 갖지 않는다.
 * 격자가 화면 밖까지 뻗어 있으므로 "보이는 자리인가"는 호출자가 allow 로 더해 검사한다.
 */
export function isGridPlacementValid(
  surface: SurfaceDef,
  cell: GridCell,
  footprint: GridFootprint,
  others: readonly GridPlacement[],
  allow?: (cell: GridCell) => boolean
): boolean {
  if (!fitsOnSurface(surface, cell, footprint)) return false;
  if (allow && !allow(cell)) return false;
  return !others.some((other) => cellsOverlap(cell, footprint, other.cell, other.footprint));
}

