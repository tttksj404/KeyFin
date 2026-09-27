import * as React from "react";
import { useWindowDimensions, type View } from "react-native";
import { Easing, Extrapolation, interpolate, useAnimatedStyle, useReducedMotion, useSharedValue, withDelay, withTiming } from "react-native-reanimated";

/**
 * 첫 화면 연출: 캐릭터가 화면 가운데를 크게 채웠다가 제자리로 줄어들며 글·입력창이 나타난다 (사용자 제안 2026-09-16).
 * 로그인·회원가입·약관·금융망 이메일이 쓴다. 시작 배율은 캐릭터 제자리 크기를 재서 화면 폭의 85% 가 되게 잡는다(로그인 150 → 2.2배, 코치 행 76 → 4.4배).
 * 앱을 켜고 화면마다 처음 볼 때 한 번만 재생하고, 동작 줄이기 설정이면 생략한다.
 */
const FILL_WIDTH_RATIO = 0.85;
const MAX_HEIGHT_RATIO = 0.55;
const HOLD_MS = 320;
const DURATION_MS = 900;
const played = new Set<string>();

export type IntroReveal = {
  characterRef: React.RefObject<View | null>;
  onCharacterLayout: () => void;
  /** 캐릭터 래퍼(Animated.View)에 준다 — 가운데·큰 상태에서 제자리·1배로 */
  characterStyle: ReturnType<typeof useAnimatedStyle>;
  /** 나머지 내용의 래퍼(Animated.View)에 준다 — 절반쯤 줄어든 뒤 올라오며 나타남 */
  revealStyle: ReturnType<typeof useAnimatedStyle>;
};

export function useIntroReveal(screenKey: string): IntroReveal {
  const reducedMotion = useReducedMotion();
  const window = useWindowDimensions();
  const skip = reducedMotion || played.has(screenKey);
  const progress = useSharedValue(skip ? 1 : 0);
  const measured = useSharedValue(skip ? 1 : 0);
  const dx = useSharedValue(0);
  const dy = useSharedValue(0);
  const scale = useSharedValue(1);
  const characterRef = React.useRef<View>(null);

  // 캐릭터의 제자리를 잰 뒤 화면 가운데에서 출발한다. 재기 전 한 프레임은 아무것도 안 보여 튀지 않는다.
  const onCharacterLayout = () => {
    if (skip || measured.value === 1) return;
    characterRef.current?.measureInWindow((x, y, width, height) => {
      dx.value = window.width / 2 - (x + width / 2);
      dy.value = window.height / 2 - (y + height / 2);
      scale.value = Math.max(1, Math.min((window.width * FILL_WIDTH_RATIO) / width, (window.height * MAX_HEIGHT_RATIO) / height));
      measured.value = 1;
      progress.value = withDelay(HOLD_MS, withTiming(1, { duration: DURATION_MS, easing: Easing.out(Easing.cubic) }));
      played.add(screenKey);
    });
  };

  const characterStyle = useAnimatedStyle(() => {
    const remaining = 1 - progress.value;
    return {
      opacity: measured.value,
      transform: [
        { translateX: dx.value * remaining },
        { translateY: dy.value * remaining },
        { scale: 1 + (scale.value - 1) * remaining },
      ],
    };
  });
  const revealStyle = useAnimatedStyle(() => {
    const shown = interpolate(progress.value, [0.45, 1], [0, 1], Extrapolation.CLAMP);
    return { opacity: measured.value === 0 ? 0 : shown, transform: [{ translateY: (1 - shown) * 12 }] };
  });

  return { characterRef, onCharacterLayout, characterStyle, revealStyle };
}
