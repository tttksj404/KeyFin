import { MessageCircleMore, X } from "lucide-react-native";
import { Pressable, ScrollView, View } from "react-native";
import Animated, { FadeIn, useAnimatedStyle } from "react-native-reanimated";

import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import type { CoachSpeechView } from "@/features/home/useCoachSpeech";
import { coachSpeechLayout, COACH_SPEECH_CLOSE_SIZE, COACH_SPEECH_CLOSE_VISUAL_SIZE } from "@/features/home/coachSpeechLayout";

import { getSceneScale, type SceneSize } from "@/features/room/model";
import { COACH_CAT_RECT } from "@/features/room/scene";
import { useCoachCatMotion } from "@/features/room/useCoachCatMotion";

// 고양이 그림은 Skia 씬이 그리고, 여기에는 탭 영역과 AI 코칭 말풍선을 얹는다.
// 고양이를 누르면 코칭 대화 화면으로 이동하고, 말풍선 아이콘은 코칭 내용만 펼친다.
export const COACH_LABEL = "코치";
export const COACH_SPEECH_HINT = "말풍선을 접습니다";
export const COACH_SPEECH_CLOSE_LABEL = "코치 말풍선 닫기";
export const COACH_SPEECH_ICON_LABEL = "코치가 할 말 보기";
/** 접힌 아이콘과 고양이 머리 위 간격(pt). 펼친 말풍선의 배치는 coachSpeechLayout에서 계산한다. */
const SPEECH_GAP = 4;
/** 접힌 대화 아이콘 버튼 크기(pt). 누르기 쉽게 hitSlop 을 더한다 */
const SPEECH_ICON_SIZE = 36;
const SPEECH_APPEAR_MS = 180;

type CoachTargetProps = {
  /** 캔버스 폭(pt). 씬 좌표를 이 폭으로 환산한다 */
  width: number;
  /** 실제 홈 표시 영역. 생략하면 캔버스 전체가 보이는 것으로 계산한다. */
  viewport?: SceneSize;
  /** 준비된 AI 코칭. 펼치면 말풍선, 접으면 대화 아이콘이다. null 이면 둘 다 없다 */
  speech?: CoachSpeechView | null;
  onPress: () => void;
};

/** 제자리 사각형을 통째로 옮기는 틀. `Animated.View` 에는 className 이 먹지 않아 자리·크기를 스타일로 준다 */
const FILL = { position: "absolute", left: 0, top: 0, right: 0, bottom: 0 } as const;

/**
 * 고양이 그림 위의 투명한 탭 영역. 씬 레이어(sceneObjects)에 놓아야 확대·이동해도 그림과 같이 움직인다.
 * 고양이가 둥둥 떠서 오가므로(useCoachCatMotion) 탭 영역과 점도 같은 오프셋으로 따라간다.
 */
function CoachTarget({ width, viewport, speech = null, onPress }: CoachTargetProps) {
  const scale = getSceneScale(width);
  const offset = useCoachCatMotion();
  const follow = useAnimatedStyle(() => ({
    transform: [{ translateX: offset.value.x * scale }, { translateY: offset.value.y * scale }],
  }));

  return (
    <Animated.View style={[FILL, follow]} pointerEvents="box-none">
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={COACH_LABEL}
        accessibilityHint="코치와 대화하는 화면을 엽니다"
        onPress={onPress}
        hitSlop={8}
        className="absolute active:opacity-80"
        style={{
          left: COACH_CAT_RECT.x * scale,
          top: COACH_CAT_RECT.y * scale,
          width: COACH_CAT_RECT.width * scale,
          height: COACH_CAT_RECT.height * scale,
        }}
      />
      {speech?.open ? (
        <CoachSpeech text={speech.text} width={width} viewport={viewport} onClose={speech.onClose} />
      ) : speech !== null ? (
        <CoachSpeechIcon scale={scale} unread={speech.unread} onPress={speech.onPressIcon} />
      ) : null}
    </Animated.View>
  );
}

/**
 * 고양이 머리 위에 준비된 AI 코칭을 표시하는 말풍선.
 * 고양이 머리 기준점 위의 칸 바닥에 왼쪽 아래 모서리를 붙인다. 부모의 이동 변환으로 고양이를 따라간다.
 * 고양이 쪽(왼쪽 아래) 모서리만 덜 둥글게 해 말하는 쪽을 가리킨다. X는 현재 코칭을 닫고 읽음 처리한다.
 */
function CoachSpeech({ text, width, viewport, onClose }: { text: string; width: number; viewport?: SceneSize; onClose: () => void }) {
  const layout = coachSpeechLayout(width, viewport);
  return (
    <View
      testID="coach-speech-placement"
      className="absolute justify-end"
      style={{ left: layout.left, top: layout.top, height: layout.maxHeight, width: layout.maxWidth }}
      pointerEvents="box-none"
    >
      <Animated.View
        entering={FadeIn.duration(SPEECH_APPEAR_MS)}
        style={{
          alignSelf: "flex-start",
          maxWidth: layout.maxWidth,
          maxHeight: layout.maxHeight,
          paddingTop: layout.closeTopSpace,
          paddingRight: layout.closeRightSpace,
        }}
        pointerEvents="box-none"
      >
        <View
          testID="coach-speech-bubble"
          style={{ maxWidth: layout.bubbleMaxWidth, maxHeight: layout.bubbleMaxHeight, paddingTop: layout.contentPaddingTop }}
          className="self-start rounded-2xl rounded-bl-sm border border-transparent bg-card px-3 pb-2 shadow-md shadow-black/20 dark:border-border dark:shadow-none"
        >
          {/* 본문은 내부 폭 전체를 쓰고, 짧으면 필요한 높이만 사용한다. */}
          <ScrollView
            testID="coach-speech-content"
            style={{ flexGrow: 0, flexShrink: 1, maxWidth: layout.contentMaxWidth, maxHeight: layout.contentMaxHeight }}
            showsVerticalScrollIndicator
            bounces={false}
          >
            <Text accessibilityLabel={`${COACH_LABEL}: ${text}`} accessibilityLiveRegion="polite" className="text-body-sm text-foreground">
              {text}
            </Text>
          </ScrollView>
        </View>
        {/* 원형 X를 우측 상단에 반쯤 겹친다. 44pt 터치 영역은 본문보다 위에 둔다. */}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={COACH_SPEECH_CLOSE_LABEL}
          accessibilityHint={COACH_SPEECH_HINT}
          onPress={onClose}
          style={{ position: "absolute", top: 0, right: 0, width: COACH_SPEECH_CLOSE_SIZE, height: COACH_SPEECH_CLOSE_SIZE, zIndex: 1 }}
          className="items-center justify-end active:opacity-80"
        >
          <View
            style={{ width: COACH_SPEECH_CLOSE_VISUAL_SIZE, height: COACH_SPEECH_CLOSE_VISUAL_SIZE }}
            className="items-center justify-center rounded-full bg-card shadow-md shadow-black/20 dark:border dark:border-border dark:shadow-none"
          >
            <Icon as={X} size={16} className="text-foreground" />
          </View>
        </Pressable>
      </Animated.View>
    </View>
  );
}

/**
 * 말풍선을 접으면 남는 대화 아이콘 버튼. 고양이 머리 위 가운데에 두고, 누르면 말풍선을 다시 펼친다.
 * 아직 직접 열어 보지 않은 AI 코칭이 있으면 오른쪽 위에 빨간 점을 단다.
 */
function CoachSpeechIcon({
  scale,
  unread,
  onPress,
}: {
  scale: number;
  unread: boolean;
  onPress: () => void;
}) {
  const catCenter = (COACH_CAT_RECT.x + COACH_CAT_RECT.width / 2) * scale;
  return (
    <Animated.View
      entering={FadeIn.duration(SPEECH_APPEAR_MS)}
      style={{
        position: "absolute",
        left: catCenter - SPEECH_ICON_SIZE / 2,
        top: COACH_CAT_RECT.y * scale - SPEECH_GAP - SPEECH_ICON_SIZE,
      }}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={
          unread ? `${COACH_SPEECH_ICON_LABEL}, 새 메시지` : COACH_SPEECH_ICON_LABEL
        }
        accessibilityHint="코치의 말풍선을 다시 펼칩니다"
        hitSlop={6}
        onPress={onPress}
        className="h-9 w-9 items-center justify-center rounded-full bg-card shadow-md shadow-black/20 active:opacity-80 dark:border dark:border-border dark:shadow-none"
      >
        <Icon as={MessageCircleMore} size={20} className="text-primary" />
        {unread ? (
          <View accessible={false} className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-card bg-destructive" />
        ) : null}
      </Pressable>
    </Animated.View>
  );
}

export { CoachTarget };
export type { CoachTargetProps };
