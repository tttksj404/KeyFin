import * as React from "react";
import { useReducedMotion } from "react-native-reanimated";

import { fromWon, toWon, type KRW } from "@/lib/money";

const DEFAULT_DURATION_MS = 900;

/** 끝에서 천천히 멈추는 곡선(ease-out cubic). 소비 분석 막대(SpendingBarRow)와 같은 느낌 */
function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * 금액이 지금 값에서 목표 값까지 굴러가며 바뀐다. 처음엔 0 에서 시작한다.
 * 화면에 보이는 숫자만 바꾸고 계산에는 쓰지 않는다(규칙 80: 금액 계산은 lib/money 의 정수 유틸만).
 * 동작 줄이기 설정이면 바로 목표 값을 돌려준다.
 */
function useCountUp(target: KRW, durationMs = DEFAULT_DURATION_MS): KRW {
  const reducedMotion = useReducedMotion();
  const [shown, setShown] = React.useState<KRW>(reducedMotion ? target : "0");
  const shownRef = React.useRef(shown);
  shownRef.current = shown;

  React.useEffect(() => {
    if (reducedMotion) {
      setShown(target);
      return;
    }
    const from = toWon(shownRef.current);
    const to = toWon(target);
    if (from === to) return;
    const delta = to - from;
    const startedAt = Date.now();
    let frame = 0;
    const tick = () => {
      const progress = Math.min(1, (Date.now() - startedAt) / durationMs);
      const scaled = BigInt(Math.round(easeOut(progress) * 1_000_000));
      setShown(fromWon(from + (delta * scaled) / 1_000_000n));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs, reducedMotion]);

  return shown;
}

export { useCountUp };
