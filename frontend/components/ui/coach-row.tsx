import * as React from "react";
import { View } from "react-native";
import Animated from "react-native-reanimated";

import { Floating } from "@/components/ui/floating";
import type { IntroReveal } from "@/components/ui/intro-reveal";
import { Sprite, type SpriteFrames } from "@/components/ui/sprite";
import { Text } from "@/components/ui/text";
import { typography } from "@/lib/theme";

type CoachRowProps = {
  /** `features/room/assets` 의 `CHARACTER_FRAMES` 포즈 묶음 */
  frames: SpriteFrames;
  /** 줄마다 `\n` 으로 나눈다. 각 줄은 말풍선 안에서 한 줄로 보인다 */
  message: string;
  /** 첫 화면 연출(useIntroReveal). 주면 캐릭터가 크게 나타났다 제자리로 줄고 말풍선이 뒤따라 나타난다 */
  intro?: IntroReveal;
};

/** Pencil CoachRow 의 캐릭터 76×112. 4px 스케일 밖 값이라 크기만 style 로 준다 */
const CHARACTER_STYLE = { width: 76, height: 112 } as const;
// Animated.View 에는 className 이 안 먹어 flex-1 만 style 로 준다
const FLEX_ONE = { flex: 1 } as const;

/** 문장의 원래 폭을 잴 때 줄바꿈이 일어나지 않을 만큼 넓은 측정 영역 */
const MEASURE_STYLE = { width: 1000 } as const;
/** 반올림으로 마지막 글자가 다음 줄로 밀리지 않게 남기는 여유 */
const FIT_MARGIN_PX = 2;
/**
 * 이보다 작게는 줄이지 않는다(15 → 10.5). 폭 360 에서 가장 긴 약관 둘째 줄이 0.75 배로 한 줄에 들어간다.
 * 더 좁거나 시스템 글자 크기를 키운 기기에서는 줄바꿈을 허용한다
 */
const MIN_MESSAGE_SCALE = 0.7;

function messageScale(boxWidth: number, naturalWidth: number): number {
  const room = boxWidth - FIT_MARGIN_PX;
  if (boxWidth === 0 || naturalWidth <= room) return 1;
  return Math.max(MIN_MESSAGE_SCALE, room / naturalWidth);
}

// 온보딩 코치 행: 둥실거리는 캐릭터 + 말풍선 카드. 홈 코치 말풍선(bg-card · border-border · rounded-lg)과 같은 스타일이다.
// Pencil 회원가입(b66wKg) · 약관(f0WyT) · 금융망 이메일(PqGvX) 캐릭터 대안의 CoachRow.
function CoachRow({ frames, message, intro }: CoachRowProps) {
  return (
    <View className="flex-row items-start gap-3">
      <Animated.View ref={intro?.characterRef} onLayout={intro?.onCharacterLayout} style={intro?.characterStyle}>
        <Floating>
          <Sprite frames={frames} style={CHARACTER_STYLE} />
        </Floating>
      </Animated.View>
      <Animated.View style={[FLEX_ONE, intro?.revealStyle]}>
        <View className="rounded-lg border border-border bg-card p-3.5">
          <CoachMessage message={message} />
        </View>
      </Animated.View>
    </View>
  );
}

// 말풍선 문장. 폰 폭이 좁아 가장 긴 줄이 넘치면 모든 줄의 글자를 같은 비율로 줄여 줄마다 한 줄에 담는다.
// 원래 폭은 화면 밖 넓은 영역에 같은 문장을 그려 잰다(웹에는 adjustsFontSizeToFit 이 없다).
function CoachMessage({ message }: { message: string }) {
  const [boxWidth, setBoxWidth] = React.useState(0);
  const [naturalWidth, setNaturalWidth] = React.useState(0);

  const scale = messageScale(boxWidth, naturalWidth);
  const { fontSize, lineHeight } = typography.label;
  const fittedStyle = scale < 1 ? { fontSize: fontSize * scale, lineHeight: lineHeight * scale } : undefined;

  return (
    <View className="overflow-hidden" onLayout={(event) => setBoxWidth(event.nativeEvent.layout.width)}>
      <View
        className="pointer-events-none absolute left-0 top-0 items-start opacity-0"
        style={MEASURE_STYLE}
        aria-hidden
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <Text className="text-label" onLayout={(event) => setNaturalWidth(event.nativeEvent.layout.width)}>
          {message}
        </Text>
      </View>
      <Text className="text-label text-foreground" style={fittedStyle}>
        {message}
      </Text>
    </View>
  );
}

export { CoachRow };
