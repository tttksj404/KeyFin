import { Cat } from "lucide-react-native";
import * as React from "react";
import { Pressable, useWindowDimensions, View } from "react-native";
import Animated, { useAnimatedStyle, useDerivedValue, useSharedValue, withTiming } from "react-native-reanimated";

import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import type { SceneRect } from "@/features/room/model";

/**
 * 첫 진입 안내의 덮개와 말풍선. 화면 레이어(Screen)에 얹혀 방뿐 아니라 사이드 버튼까지 덮는다 —
 * 방 레이어에 두면 그 위에 그려지는 알림·상점·옷장 버튼을 가리킬 수 없다 (2026-09-20).
 *
 * 색·테두리는 안쪽의 보통 View·Pressable 이 className 으로 맡는다. `Animated.View` 에는 className 이 전달되지 않아
 * (2026-09-20 웹에서 확인: class 가 붙지 않고 위치도 static 으로 남았다) 자리와 크기만 애니메이션 스타일로 준다.
 */
const DIM_CLASS = "h-full w-full bg-black/50";
const ABSOLUTE = { position: "absolute" } as const;
/** 가리키는 것 둘레로 조금 더 비워 둘 여백(pt) — 딱 붙으면 답답해 보인다 */
const SPOTLIGHT_PADDING = 6;
const FADE_MS = 260;
/** 단계가 넘어갈 때 비워 둔 자리가 옮겨 가는 시간 */
const MOVE_MS = 320;

/** 말풍선과 비워 둔 자리 사이 간격, 화면 가장자리 여백, 최대 폭(pt) */
const BUBBLE_GAP = 12;
const BUBBLE_MARGIN = 16;
const BUBBLE_MAX_WIDTH = 300;
/** 아래에 이만큼도 안 남으면 가리키는 것 위에 붙인다 */
const BUBBLE_MIN_SPACE = 150;

export const SPOTLIGHT_LABEL = "안내 다음으로";
export const GUIDE_NEXT_LABEL = "다음";
export const GUIDE_DONE_LABEL = "알겠어요";
export const GUIDE_SKIP_LABEL = "그만 보기";

type RoomGuideOverlayProps = {
  /** 가리킬 것의 화면 사각형(pt). 아직 재지 못했으면 null — 덮개를 그리지 않는다 */
  rect: SceneRect | null;
  message: string;
  /** "3/6" */
  progress: string;
  isLast: boolean;
  onNext: () => void;
  onSkip: () => void;
};

function RoomGuideOverlay({ rect, message, progress, isLast, onNext, onSkip }: RoomGuideOverlayProps) {
  const screen = useWindowDimensions();

  const holeX = rect ? rect.x - SPOTLIGHT_PADDING : 0;
  const holeY = rect ? rect.y - SPOTLIGHT_PADDING : 0;
  const holeW = rect ? rect.width + SPOTLIGHT_PADDING * 2 : 0;
  const holeH = rect ? rect.height + SPOTLIGHT_PADDING * 2 : 0;

  // 단계가 바뀌면 비워 둔 자리가 미끄러지듯 옮겨 간다. 네 장과 테두리가 같은 값을 보고 움직인다.
  const left = useDerivedValue(() => withTiming(holeX, { duration: MOVE_MS }), [holeX]);
  const top = useDerivedValue(() => withTiming(holeY, { duration: MOVE_MS }), [holeY]);
  const holeWidth = useDerivedValue(() => withTiming(holeW, { duration: MOVE_MS }), [holeW]);
  const holeHeight = useDerivedValue(() => withTiming(holeH, { duration: MOVE_MS }), [holeH]);

  const appeared = useSharedValue(0);

  React.useEffect(() => {
    appeared.value = withTiming(1, { duration: FADE_MS });
  }, [appeared]);

  const fade = useAnimatedStyle(() => ({ opacity: appeared.value }));
  const topStyle = useAnimatedStyle(() => ({ top: 0, left: 0, right: 0, height: Math.max(0, top.value) }));
  const bottomStyle = useAnimatedStyle(() => ({ top: top.value + holeHeight.value, left: 0, right: 0, bottom: 0 }));
  const leftStyle = useAnimatedStyle(() => ({ top: top.value, left: 0, width: Math.max(0, left.value), height: holeHeight.value }));
  const rightStyle = useAnimatedStyle(() => ({ top: top.value, left: left.value + holeWidth.value, right: 0, height: holeHeight.value }));

  // 네 장은 각자 터치를 받는다 — 한 장으로 감싸면 비워 둔 자리까지 덮여 가리키는 것을 누를 수 없다.
  const dim = (style: ReturnType<typeof useAnimatedStyle>, key: string) => (
    <Animated.View key={key} style={[ABSOLUTE, style]}>
      <Pressable className={DIM_CLASS} accessibilityRole="button" accessibilityLabel={SPOTLIGHT_LABEL} onPress={onNext} />
    </Animated.View>
  );

  const bubble = bubbleBox(rect, screen);

  return (
    <View className="absolute inset-0" style={FILL_NONE}>
      {rect === null ? null : (
        <Animated.View style={[{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }, fade]}>
          {dim(topStyle, "top")}
          {dim(bottomStyle, "bottom")}
          {dim(leftStyle, "left")}
          {dim(rightStyle, "right")}
        </Animated.View>
      )}
      <View
        className="absolute gap-2 rounded-lg border border-border bg-card p-3"
        style={{ left: bubble.x, top: bubble.y, width: bubble.width }}
        accessibilityLiveRegion="polite"
      >
        <View className="flex-row items-start gap-2">
          <View className="h-6 w-6 items-center justify-center rounded-full bg-accent" accessible={false}>
            <Icon as={Cat} size={14} className="text-foreground" />
          </View>
          <Text className="flex-1 text-body-sm text-foreground">{message}</Text>
        </View>
        <View className="flex-row items-center justify-between">
          <Text className="text-caption tabular-nums text-muted-foreground">{progress}</Text>
          <View className="flex-row items-center gap-4">
            {isLast ? null : (
              <Pressable accessibilityRole="button" hitSlop={12} onPress={onSkip} className="active:opacity-70">
                <Text className="text-caption text-muted-foreground">{GUIDE_SKIP_LABEL}</Text>
              </Pressable>
            )}
            <Pressable accessibilityRole="button" hitSlop={12} onPress={onNext} className="active:opacity-70">
              <Text className="text-label text-primary">{isLast ? GUIDE_DONE_LABEL : GUIDE_NEXT_LABEL}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </View>
  );
}

/** 자신은 터치를 받지 않고 자식만 받는다 — 말풍선 밖의 빈 곳은 아래 덮개가 받는다 */
const FILL_NONE = { pointerEvents: "box-none" } as const;

/**
 * 말풍선 자리. 가리키는 것 아래에 붙이되 아래가 좁으면 위로 올리고, 좌우는 화면 안으로 가둔다.
 * 높이는 글 길이에 따라 달라져 재지 않는다. 아직 대상 자리를 모르면(rect null) 화면 아래쪽 가운데에 둔다 —
 * 덮개 없이 설명만 먼저 보여 주는 편이 아무것도 안 보이는 것보다 낫다.
 */
function bubbleBox(rect: SceneRect | null, screen: { width: number; height: number }) {
  const width = Math.min(BUBBLE_MAX_WIDTH, screen.width - BUBBLE_MARGIN * 2);
  if (rect === null) return { x: (screen.width - width) / 2, y: screen.height - BUBBLE_MIN_SPACE - BUBBLE_MARGIN, width };
  const below = rect.y + rect.height + SPOTLIGHT_PADDING + BUBBLE_GAP;
  const fitsBelow = screen.height - below >= BUBBLE_MIN_SPACE;
  const y = fitsBelow ? below : Math.max(BUBBLE_MARGIN, rect.y - SPOTLIGHT_PADDING - BUBBLE_GAP - BUBBLE_MIN_SPACE);
  const x = Math.min(Math.max(BUBBLE_MARGIN, rect.x + rect.width / 2 - width / 2), screen.width - BUBBLE_MARGIN - width);
  return { x, y, width };
}

export { RoomGuideOverlay };
export type { RoomGuideOverlayProps };
