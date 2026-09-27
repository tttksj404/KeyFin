import * as React from "react";
import type { ViewProps } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

type FloatingProps = ViewProps & {
  /** 위아래로 오가는 거리(px). */
  distance?: number;
  /** 한 번 오르내리는 데 걸리는 시간(ms). */
  period?: number;
};

const DEFAULT_DISTANCE = 6;
const DEFAULT_PERIOD = 2_400;

// 캐릭터 정지 이미지를 둥실거리게 하는 래퍼. 방 씬과 같은 Reanimated 코드 모션이라 별도 에셋이 없고,
// 동작 줄이기 설정이면 움직이지 않는다.
function Floating({ distance = DEFAULT_DISTANCE, period = DEFAULT_PERIOD, style, ...props }: FloatingProps) {
  const reducedMotion = useReducedMotion();
  const offset = useSharedValue(0);

  React.useEffect(() => {
    if (reducedMotion) return;
    offset.value = withRepeat(
      withTiming(-distance, { duration: period / 2, easing: Easing.inOut(Easing.sin) }),
      -1,
      true
    );
    return () => cancelAnimation(offset);
  }, [offset, reducedMotion, distance, period]);

  const floating = useAnimatedStyle(() => ({ transform: [{ translateY: reducedMotion ? 0 : offset.value }] }));

  return <Animated.View style={[floating, style]} {...props} />;
}

export { Floating };
