import * as React from "react";
import { View, type ViewProps } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";

import { cn } from "@/lib/utils";

type FillBarProps = ViewProps & {
  /** 0~100 */
  percent: number;
  /** 채움 색. 봉투 정체성 색이면 `envelopeTone(id).bar`, 상태색이면 `bg-positive` 등 */
  fillClassName?: string;
  /** 트랙 높이 등. 기본 `h-2` */
  className?: string;
  /** 주면 화면에 들어올 때 0 에서 percent 까지 차오른다(ms 뒤 시작). 없으면 바로 채워진 채 그린다 */
  fillDelay?: number;
};

const FILL_MS = 900;
/** Animated.View 는 NativeWind className 대상이 아니라 style 로 높이를 채운다 */
const FULL_HEIGHT = { height: "100%" } as const;

// 가로 진행 막대 한 종류. 소비 분석 막대·예산 탭 사용률 막대가 같이 쓴다. 접근성 prop 은 트랙 View 에 붙는다.
function FillBar({ percent, fillClassName = "bg-primary", className, fillDelay, ...trackProps }: FillBarProps) {
  return (
    <View className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)} {...trackProps}>
      {fillDelay === undefined ? (
        <View className={cn("h-full rounded-full", fillClassName)} style={{ width: `${percent}%` }} />
      ) : (
        <FillingBar percent={percent} delay={fillDelay} fillClassName={fillClassName} />
      )}
    </View>
  );
}

// 트랙 폭을 재서 0 → percent 만큼 px 로 차오른다. 동작 줄이기 설정이면 처음부터 채워 둔다.
function FillingBar({ percent, delay, fillClassName }: { percent: number; delay: number; fillClassName: string }) {
  const reducedMotion = useReducedMotion();
  const [trackWidth, setTrackWidth] = React.useState(0);
  const progress = useSharedValue(reducedMotion ? 1 : 0);

  React.useEffect(() => {
    if (reducedMotion || trackWidth === 0) return;
    progress.value = withDelay(delay, withTiming(1, { duration: FILL_MS, easing: Easing.out(Easing.cubic) }));
    return () => cancelAnimation(progress);
  }, [progress, reducedMotion, trackWidth, delay]);

  const fill = useAnimatedStyle(() => ({ width: (trackWidth * percent * progress.value) / 100 }));

  return (
    <View className="h-full w-full" onLayout={(event) => setTrackWidth(event.nativeEvent.layout.width)}>
      <Animated.View style={[FULL_HEIGHT, fill]}>
        <View className={cn("h-full rounded-full", fillClassName)} />
      </Animated.View>
    </View>
  );
}

export { FillBar };
export type { FillBarProps };
