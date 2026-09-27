import { useRouter } from "expo-router";
import * as React from "react";

import { useCurrentBudget } from "@/features/budget/api/queries";
import { useRoom } from "@/features/room/api/queries";
import { MOVING_IN_COPY, RoomWaiting } from "@/features/room/components/RoomWaiting";

/**
 * 입주 연출에서 넘어왔다는 표시. 홈은 방 그림을 다 읽을 때까지 대기 화면을 덮어 두는데(HomeScreen),
 * 이 값이 있으면 그동안 입주 문구를 그대로 이어서 보여 준다 — 입주 화면이 방이 다 그려질 때까지 이어지는 것처럼 보인다.
 */
export const MOVING_IN_FROM = "moving-in";
const HOME_AFTER_MOVING_IN = { pathname: "/", params: { from: MOVING_IN_FROM } } as const;

/** 방 데이터가 금방 와도 연출이 보이도록 최소한 이만큼은 머문다 */
const MIN_VISIBLE_MS = 1_500;

// Pencil character-moving-in (sla4v). GET /room 을 미리 받아 두고 홈으로 넘긴다 (PAGE-08).
// 방 그림(스프라이트)은 여기서 미리 읽어 둘 수 없다 — Skia useImage 는 부르는 곳마다 따로 읽어 캐시가 없다(RoomScene).
// 그래서 그림을 기다리는 일은 홈이 같은 화면(RoomWaiting)을 덮어 이어받는다.
function MovingInScreen() {
  const router = useRouter();
  const room = useRoom();
  // 예산 승인 직후라 현재 예산 캐시가 새로 받는 중이다. 여기서 구독해 두면 홈에 들어갈 때 이미 CONFIRMED 라
  // 홈이 확정 화면으로 되돌려 보내는 깜빡임이 없다(2026-09-14).
  const budget = useCurrentBudget();
  const [waited, setWaited] = React.useState(false);

  React.useEffect(() => {
    const timer = setTimeout(() => setWaited(true), MIN_VISIBLE_MS);
    return () => clearTimeout(timer);
  }, []);

  // 방·예산을 못 받아도 홈이 스스로 오류·재시도를 보여주므로 여기서 붙잡지 않는다. 받는 중일 때만 기다린다.
  const settled = !room.isPending && !budget.isFetching;

  React.useEffect(() => {
    if (waited && settled) router.replace(HOME_AFTER_MOVING_IN);
  }, [waited, settled, router]);

  return <RoomWaiting copy={MOVING_IN_COPY} />;
}

export { MovingInScreen, MIN_VISIBLE_MS };
