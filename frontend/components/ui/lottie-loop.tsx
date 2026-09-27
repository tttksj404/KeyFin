import LottieView, { type AnimationObject } from "lottie-react-native";
import { View } from "react-native";
import { useReducedMotion } from "react-native-reanimated";

type LottieLoopProps = {
  /** `require("@/assets/lottie/<name>.json")` — Metro 가 JSON 을 객체로 준다 */
  source: AnimationObject;
  width: number;
  height: number;
  accessibilityLabel?: string;
};

// Lottie 반복 재생. 기기는 lottie-react-native 네이티브 뷰, 웹은 같은 패키지의 웹 구현(@lottiefiles/dotlottie-react)이 그린다.
// 동작 줄이기 설정이면 첫 프레임에 멈춰 둔다. LottieView 는 접근성 prop 을 받지 않아 감싸는 View 에 붙인다.
function LottieLoop({ source, width, height, accessibilityLabel }: LottieLoopProps) {
  const reducedMotion = useReducedMotion();

  return (
    <View accessible={accessibilityLabel !== undefined} accessibilityLabel={accessibilityLabel}>
      <LottieView
        source={source}
        autoPlay={!reducedMotion}
        loop
        progress={reducedMotion ? 0 : undefined}
        style={{ width, height }}
      />
    </View>
  );
}

export { LottieLoop };
export type { LottieLoopProps };
