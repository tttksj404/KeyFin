import * as React from "react";
import { cancelAnimation, Easing, runOnJS, useSharedValue, withRepeat, withTiming, type SharedValue } from "react-native-reanimated";

import { pickWaypoint, segmentCrossesPolygon, travelDurationMs, type ScenePoint, type ScenePolygon } from "@/features/room/model";
import { CHARACTER_MOTION, CHARACTER_SIZE } from "@/features/room/scene";

/** 스프라이트가 화면 좌우 밖으로 잘리지 않도록 목적지 x 를 폭의 절반 + 여유만큼 안쪽으로 제한한다 */
const X_INSET = CHARACTER_SIZE.width / 2 + 6;

export type CharacterWalker = {
  /** 발끝 x (씬 단위) */
  x: SharedValue<number>;
  /** 발끝 y (씬 단위) */
  y: SharedValue<number>;
  /** 1 = 오른쪽을 봄, -1 = 왼쪽(미러링) */
  facing: SharedValue<number>;
  /** 이동 중이면 1 */
  moving: SharedValue<number>;
  /** 이동 중 0→1→0 을 반복하는 잔걸음 위상 */
  bobPhase: SharedValue<number>;
  /** 0→1→0 을 천천히 반복하는 호흡 위상 */
  breathPhase: SharedValue<number>;
  /** 소파에 앉아 있으면 1 */
  sitting: SharedValue<number>;
};

type UseCharacterWalkerOptions = {
  polygon: ScenePolygon;
  blocked: readonly ScenePolygon[];
  start?: ScenePoint;
  /** false 면 걷지 않고 제자리에서 호흡만 한다 */
  walking?: boolean;
  /** 소파에 앉을 자리. null 이면 앉지 않고 걷기만 한다 */
  seat?: ScenePoint | null;
};

/**
 * 바닥 다각형 안에서 랜덤 웨이포인트로 걸어 다니는 캐릭터의 상태.
 * 일정 시간 쉬었다가(3~6초) 가구를 피해 다음 목적지를 고르고, 일정 속도로 이동한다.
 * 목적지는 가끔 소파여서, 도착하면 잠깐 앉았다가(4~8초) 일어나 다시 걷는다.
 * 위치·방향·위상은 셰어드 값이라 Skia 캔버스가 React 리렌더 없이 매 프레임 읽는다.
 */
export function useCharacterWalker({
  polygon,
  blocked,
  start = CHARACTER_MOTION.start,
  walking = true,
  seat = null,
}: UseCharacterWalkerOptions): CharacterWalker {
  const x = useSharedValue(start.x);
  const y = useSharedValue(start.y);
  const facing = useSharedValue(1);
  const moving = useSharedValue(0);
  const bobPhase = useSharedValue(0);
  const breathPhase = useSharedValue(0);
  const sitting = useSharedValue(0);

  React.useEffect(() => {
    breathPhase.value = withRepeat(
      withTiming(1, { duration: CHARACTER_MOTION.breath.periodMs, easing: Easing.inOut(Easing.sin) }),
      -1,
      true
    );
    return () => cancelAnimation(breathPhase);
  }, [breathPhase]);

  React.useEffect(() => {
    if (!walking) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let alive = true;

    const wait = () => {
      const { min, max } = CHARACTER_MOTION.idleWaitMs;
      timer = setTimeout(walk, min + Math.random() * (max - min));
    };

    const sit = () => {
      if (!alive) return;
      // 앉은 그림은 정면을 보므로 미러링을 풀어 둔다. 일어설 때 다시 진행 방향으로 정해진다.
      facing.value = 1;
      sitting.value = 1;
      const { min, max } = CHARACTER_MOTION.sitMs;
      timer = setTimeout(() => {
        if (!alive) return;
        sitting.value = 0;
        wait();
      }, min + Math.random() * (max - min));
    };

    const arrive = (seated: boolean) => {
      if (!alive) return;
      moving.value = 0;
      cancelAnimation(bobPhase);
      bobPhase.value = withTiming(0, { duration: 150 });
      if (seated) sit();
      else wait();
    };

    /** 소파가 있으면 가끔 그리로 간다. 가는 길이 다른 가구에 막히면 이번에는 포기하고 아무 곳으로 간다 */
    const pickTarget = (from: ScenePoint): { point: ScenePoint; seated: boolean } | null => {
      if (seat && Math.random() < CHARACTER_MOTION.sitChance && !blocked.some((area) => segmentCrossesPolygon(from, seat, area))) {
        return { point: seat, seated: true };
      }
      const point = pickWaypoint({ from, polygon, blocked, xInset: X_INSET });
      return point ? { point, seated: false } : null;
    };

    const walk = () => {
      if (!alive) return;
      const from = { x: x.value, y: y.value };
      const target = pickTarget(from);
      if (!target) {
        timer = setTimeout(walk, 1000);
        return;
      }
      const duration = travelDurationMs(from, target.point, CHARACTER_MOTION.speed);
      facing.value = target.point.x < from.x ? -1 : 1;
      moving.value = 1;
      bobPhase.value = withRepeat(withTiming(1, { duration: CHARACTER_MOTION.bob.periodMs / 2 }), -1, true);
      x.value = withTiming(target.point.x, { duration, easing: Easing.inOut(Easing.quad) });
      y.value = withTiming(target.point.y, { duration, easing: Easing.inOut(Easing.quad) }, (finished) => {
        if (finished) runOnJS(arrive)(target.seated);
      });
    };

    timer = setTimeout(walk, 1500);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
      sitting.value = 0;
      cancelAnimation(x);
      cancelAnimation(y);
      cancelAnimation(bobPhase);
    };
  }, [walking, polygon, blocked, seat, x, y, facing, moving, bobPhase, sitting]);

  return { x, y, facing, moving, bobPhase, breathPhase, sitting };
}
