import { useFrameCallback, useReducedMotion, useSharedValue, type SharedValue } from "react-native-reanimated";

import type { ScenePoint } from "@/features/room/model";
import { COACH_CAT_FLOAT_HEIGHT, COACH_CAT_STROLL_RANGE } from "@/features/room/scene";

/**
 * 코치 고양이의 둥둥 뜨기 + 느린 산책 (사용자 요청 2026-09-23). 고양이는 코칭 대화로 가는 버튼이라
 * 누르기 어렵지 않게 활동량을 최소로 둔다 — 제자리 둘레 좌우 십여 단위만 오가고, 대부분은 멈춰서 떠 있기만 한다.
 *
 * 그림(Skia 씬)과 탭 영역(홈 씬 레이어)이 따로 그려지므로 둘이 각자 이 훅을 쓴다. 위치가 프레임 시각만의 함수라
 * 같은 프레임에서는 두 쪽이 같은 값을 얻어 어긋나지 않는다. 동작 줄이기 설정이면 제자리에 가만히 있다.
 */

/** 한 번 오르내리는 주기 */
const FLOAT_PERIOD_MS = 2600;

/** 산책 지점(제자리 기준 씬 단위 오프셋). 차례로 돌고 처음으로 돌아온다. */
const HOME: ScenePoint = { x: 0, y: 0 };
const STROLL_POINTS: readonly ScenePoint[] = [
  HOME,
  { x: COACH_CAT_STROLL_RANGE.right, y: COACH_CAT_STROLL_RANGE.down },
  HOME,
  { x: -COACH_CAT_STROLL_RANGE.left, y: 2 },
];
/** 한 지점에 머무는 시간과 다음 지점까지 옮겨 가는 시간 */
const STROLL_REST_MS = 4000;
const STROLL_MOVE_MS = 1800;
const STROLL_LEG_MS = STROLL_REST_MS + STROLL_MOVE_MS;

/** 제자리(COACH_CAT_ANCHOR) 기준 오프셋. y 는 음수가 위쪽이다 */
export function coachCatOffsetAt(timeMs: number): ScenePoint {
  "worklet";
  const float = -COACH_CAT_FLOAT_HEIGHT * (0.5 - 0.5 * Math.cos((2 * Math.PI * timeMs) / FLOAT_PERIOD_MS));

  const leg = Math.floor(timeMs / STROLL_LEG_MS);
  const within = timeMs - leg * STROLL_LEG_MS;
  const from = STROLL_POINTS[leg % STROLL_POINTS.length] ?? HOME;
  const to = STROLL_POINTS[(leg + 1) % STROLL_POINTS.length] ?? HOME;
  const progress = within <= STROLL_REST_MS ? 0 : (within - STROLL_REST_MS) / STROLL_MOVE_MS;
  // 출발·도착을 부드럽게 (ease-in-out)
  const eased = 0.5 - 0.5 * Math.cos(Math.PI * progress);

  return { x: from.x + (to.x - from.x) * eased, y: from.y + (to.y - from.y) * eased + float };
}

export function useCoachCatMotion(): SharedValue<ScenePoint> {
  const reducedMotion = useReducedMotion();
  const offset = useSharedValue<ScenePoint>({ x: 0, y: 0 });

  useFrameCallback((frame) => {
    offset.value = coachCatOffsetAt(frame.timestamp);
  }, !reducedMotion);

  return offset;
}
