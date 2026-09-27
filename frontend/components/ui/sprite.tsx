import * as React from "react";
import { Image, View, type ImageSourcePropType, type StyleProp, type ViewStyle } from "react-native";
import { useReducedMotion } from "react-native-reanimated";

/**
 * 캐릭터 포즈 한 벌. `base` 만 있으면 정지 이미지고, 프레임을 더 주면 그만큼 움직인다.
 * 프레임은 base 와 **같은 크기·같은 발끝 위치**의 PNG 여야 겹쳤을 때 몸이 튀지 않는다.
 */
export type SpriteFrames = {
  base: ImageSourcePropType;
  /** 눈 감은 프레임. 2.5~5초에 한 번 120ms 동안 보인다 */
  blink?: ImageSourcePropType;
  /** 동작 프레임(손 위치·팔 높이가 다른 것). base 와 번갈아 몇 번 움직이고 잠시 쉰다 */
  motion?: readonly ImageSourcePropType[];
};

type SpriteProps = {
  frames: SpriteFrames;
  /** 이미지 크기. 4px 스케일 밖 값이라 style 로 받는다 */
  style: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
};

const BLINK_MS = 120;
const BLINK_GAP_MS: readonly [number, number] = [2_500, 5_000];
const MOTION_STEP_MS = 360;
const MOTION_STEPS = 6;
const MOTION_REST_MS: readonly [number, number] = [1_800, 3_200];
// 웹의 RN Image 는 크기를 안 주면 원본 픽셀 크기로 그려지므로(절대 위치 네 변만으로는 안 잡힘) 100% 를 명시한다
const FILL = { position: "absolute", top: 0, left: 0, width: "100%", height: "100%" } as const;

function randomBetween([min, max]: readonly [number, number]): number {
  return min + Math.random() * (max - min);
}

/**
 * 스프라이트 시트 없이 PNG 몇 장을 바꿔 끼워 "움직이는 느낌"을 내는 캐릭터 이미지 (2026-09-16, UI 개선 3순위).
 * 깜빡임과 동작은 서로 독립인 타이머이고, 프레임은 전부 미리 그려 두고 보이는 것만 바꿔 첫 전환에서 깜빡이지 않는다.
 * 동작 줄이기 설정이면 base 만 보인다. 둥실거림은 바깥의 `Floating` 이 맡는다.
 */
function Sprite({ frames, style, accessibilityLabel }: SpriteProps) {
  const reducedMotion = useReducedMotion();
  const [blinking, setBlinking] = React.useState(false);
  const [motionIndex, setMotionIndex] = React.useState<number | null>(null);
  const motion = frames.motion ?? [];

  React.useEffect(() => {
    if (reducedMotion || frames.blink === undefined) return;
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(() => {
        setBlinking(true);
        timer = setTimeout(() => {
          setBlinking(false);
          schedule();
        }, BLINK_MS);
      }, randomBetween(BLINK_GAP_MS));
    };
    schedule();
    return () => clearTimeout(timer);
  }, [reducedMotion, frames.blink]);

  React.useEffect(() => {
    if (reducedMotion || motion.length === 0) return;
    let timer: ReturnType<typeof setTimeout>;
    const burst = (step: number) => {
      if (step >= MOTION_STEPS) {
        setMotionIndex(null);
        timer = setTimeout(() => burst(0), randomBetween(MOTION_REST_MS));
        return;
      }
      setMotionIndex(step % 2 === 0 ? step / 2 % motion.length : null);
      timer = setTimeout(() => burst(step + 1), MOTION_STEP_MS);
    };
    timer = setTimeout(() => burst(0), randomBetween(MOTION_REST_MS));
    return () => clearTimeout(timer);
  }, [reducedMotion, motion.length]);

  const active = blinking && frames.blink !== undefined ? frames.blink : motionIndex === null ? frames.base : motion[motionIndex];
  const layers = [frames.base, ...(frames.blink ? [frames.blink] : []), ...motion];

  return (
    <View style={style} accessible={accessibilityLabel !== undefined} accessibilityRole="image" accessibilityLabel={accessibilityLabel}>
      {layers.map((source, index) => (
        <Image
          key={index}
          source={source}
          style={[FILL, { opacity: source === active ? 1 : 0 }]}
          resizeMode="contain"
          accessible={false}
        />
      ))}
    </View>
  );
}

export { Sprite };
export type { SpriteProps };
