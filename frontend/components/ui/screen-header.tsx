import { ChevronLeft } from "lucide-react-native";
import * as React from "react";
import { Pressable, View } from "react-native";
import Animated, { Extrapolation, interpolate, runOnJS, useAnimatedReaction, useAnimatedStyle } from "react-native-reanimated";
import { SafeAreaInsetsContext } from "react-native-safe-area-context";

import { Icon } from "@/components/ui/icon";
import { HEADER_CONTENT_GAP, useHeaderHeight, useScreenScroll } from "@/components/ui/screen";
import { Text } from "@/components/ui/text";
import { cn } from "@/lib/utils";

/** 이만큼 스크롤하는 동안 헤더가 서서히 투명해진다 (2026-09-16 사용자 요청으로 48 → 120) */
const FADE_DISTANCE = 120;

type ScreenHeaderProps = {
  title: string;
  /** 없으면 뒤로가기 버튼을 그리지 않는다(홈에서 강제로 온 예산 확정처럼 돌아갈 곳이 없을 때) */
  onBack?: () => void;
  /** 오른쪽 끝 액션 — '전체 선택' 텍스트 버튼, '+' 아이콘 버튼 등 */
  right?: React.ReactNode;
  /** 제목 행을 통째로 바꿀 때(홈의 두 줄 인사말). 주면 title·onBack·right 는 쓰지 않는다 */
  children?: React.ReactNode;
  /** 온보딩처럼 헤더를 면으로 세우지 않고 바탕색과 하나로 둘 때 — 흰 면·보더·그림자 없음 (2026-09-16 사용자 결정) */
  flat?: boolean;
  className?: string;
};

const OVERLAY = { position: "absolute", top: 0, left: 0, right: 0, zIndex: 10 } as const;

/**
 * 화면 헤더는 이 한 종류다: `<` + text-h1 제목 (+ 오른쪽 액션). Pencil `ScreenHeader` 컴포넌트(tdgU8)와 같다.
 * tint 배경 위에 탭바와 짝이 되는 흰 면이다 — 상태바 영역까지 직접 칠하고(라우트에 SafeAreaView 를 두지 않는다),
 * 하단 보더 + 아래 그림자(다크는 보더만), 본문과는 24 를 띄운다(2026-09-16 사용자 결정).
 * 제목 행은 상태바 아래 80 높이(`min-h-20`)에 세로 가운데 — 40 이 좁다는 피드백으로 두 배(2026-09-16).
 * 뒤로가기 화살표는 44×44 상자 가운데에 두어 제목 글자와 같은 가로선에 놓이고(2026-09-23 코치 화면에서 어긋나 보인다는 피드백) 터치 영역도 44 가 된다.
 * 상자 왼쪽을 10 만큼 당겨 화살표 자체는 예전처럼 좌우 여백 24 자리에 온다.
 *
 * `Screen` 안에서는 본문 위에 떠 있다가 스크롤하면 투명해지고 제목·뒤로가기도 같이 사라진다. 맨 위로 돌아오면 다시 나타난다.
 * 그동안 헤더 자리는 같은 높이의 빈 공간이 흐름에 남아 있어, 스크롤이 없는 상태에서도 배치가 같다.
 * `Screen` 밖(스크롤 없는 화면)에서는 흐름 안의 고정 바다.
 */
function ScreenHeader({ title, onBack, right, children, flat = false, className }: ScreenHeaderProps) {
  const scroll = useScreenScroll();
  const insets = React.useContext(SafeAreaInsetsContext);
  const headerHeight = useHeaderHeight();
  const [hidden, setHidden] = React.useState(false);

  const fadeStyle = useAnimatedStyle(() => ({
    opacity: scroll ? interpolate(scroll.scrollY.value, [0, FADE_DISTANCE], [1, 0], Extrapolation.CLAMP) : 1,
  }));
  // 투명해진 헤더가 탭을 가로채지 않도록, 완전히 사라진 동안은 터치를 본문에 넘긴다
  useAnimatedReaction(
    () => (scroll ? scroll.scrollY.value >= FADE_DISTANCE : false),
    (isHidden, previous) => {
      if (isHidden !== previous) runOnJS(setHidden)(isHidden);
    }
  );

  const bar = (
    <View
      className={cn(
        "px-6",
        flat ? "bg-background" : "border-b border-border bg-card shadow-md shadow-black/10 dark:shadow-none"
      )}
      style={{ paddingTop: insets?.top ?? 0 }}
    >
      <View className="min-h-20 justify-center">
      {children ?? (
        <View className="flex-row items-center gap-3">
          {onBack === undefined ? null : (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="뒤로"
              onPress={onBack}
              className="-ml-2.5 h-touch w-touch items-center justify-center"
            >
              <Icon as={ChevronLeft} size={24} className="text-foreground" />
            </Pressable>
          )}
          <Text className="flex-1 text-h1 text-foreground" accessibilityRole="header" numberOfLines={1}>
            {title}
          </Text>
          {right}
        </View>
      )}
      </View>
    </View>
  );

  if (scroll === null) return <View className={cn("mb-6", className)}>{bar}</View>;

  return (
    <>
      <View style={{ height: headerHeight + HEADER_CONTENT_GAP }} accessible={false} />
      <Animated.View
        style={[OVERLAY, fadeStyle]}
        pointerEvents={hidden ? "none" : "box-none"}
        className={className}
        accessibilityElementsHidden={hidden}
        importantForAccessibility={hidden ? "no-hide-descendants" : "auto"}
      >
        {bar}
      </Animated.View>
    </>
  );
}

export { ScreenHeader };
