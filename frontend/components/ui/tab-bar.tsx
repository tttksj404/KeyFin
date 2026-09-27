import type { Tabs } from "expo-router";
import { Calculator, House, User, Wallet, type LucideIcon } from "lucide-react-native";
import * as React from "react";
import { Pressable, View, type LayoutChangeEvent } from "react-native";
import Animated, { useAnimatedStyle, useReducedMotion, useSharedValue, withSpring } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { getColors } from "@/lib/theme";
import { cn } from "@/lib/utils";

type TabBarProps = Parameters<NonNullable<React.ComponentProps<typeof Tabs>["tabBar"]>>[0];

// Pencil 홈 BottomTabBar (NaYk9) 의 Tab-* 프레임 안 아이콘 이름 = lucide 이름
const TAB_ICONS: Record<string, LucideIcon> = {
  index: House,
  assets: Wallet,
  budget: Calculator,
  my: User,
};

// Pencil Tabs 프레임 padding [12,16,8,16]. 홈 인디케이터 영역은 safe area 로 대체한다.
const MIN_BOTTOM_INSET = 8;
/** 탭 행의 위 여백과 탭 높이(h-12) — 인디케이터를 탭과 같은 자리에 겹치기 위한 값.
 * 위 여백은 12 에서 활성 영역 위로 2 를 더 띄웠다(사용자 요청 2026-09-23). 12 가 아니라 클래스 대신 스타일로 준다 */
const TAB_TOP = 14;
const TAB_HEIGHT = 48;
const INDICATOR_SPRING = { damping: 18, stiffness: 220, mass: 0.8 } as const;
type TabLayout = { x: number; width: number };
/** 헤더(shadow-md, black/10)와 짝이 되는 위쪽 그림자. NativeWind 그림자 클래스는 아래 방향만 있어 스타일로 두고, 색은 토큰 black + 10% 알파다 (2026-09-16) */
const TAB_BAR_SHADOW = { boxShadow: `0 -2px 8px ${getColors("light").black}1A` } as const;

// 활성 표시(연보라 네모)는 탭마다 그리지 않고 하나를 두고 눌린 탭 자리로 미끄러뜨린다 (사용자 제안 2026-09-16).
// 탭 폭은 라벨에 따라 달라 각 탭의 자리를 재서 쓴다. 첫 자리는 튀지 않게 바로 놓고, 그다음부터 스프링으로 옮긴다.
function TabBar({ state, descriptors, navigation }: TabBarProps) {
  const insets = useSafeAreaInsets();
  const reducedMotion = useReducedMotion();
  const [layouts, setLayouts] = React.useState<Record<string, TabLayout>>({});
  const indicatorX = useSharedValue(0);
  const indicatorWidth = useSharedValue(0);
  const placed = useSharedValue(0);

  const activeKey = state.routes[state.index]?.key;
  const active = activeKey === undefined ? undefined : layouts[activeKey];
  const activeX = active?.x;
  const activeWidth = active?.width;

  React.useEffect(() => {
    if (activeX === undefined || activeWidth === undefined) return;
    if (placed.get() === 0 || reducedMotion) {
      indicatorX.set(activeX);
      indicatorWidth.set(activeWidth);
      placed.set(1);
      return;
    }
    indicatorX.set(withSpring(activeX, INDICATOR_SPRING));
    indicatorWidth.set(withSpring(activeWidth, INDICATOR_SPRING));
  }, [activeX, activeWidth, reducedMotion, indicatorX, indicatorWidth, placed]);

  const indicatorStyle = useAnimatedStyle(() => ({
    opacity: placed.value,
    width: indicatorWidth.value,
    transform: [{ translateX: indicatorX.value }],
  }));

  const rememberLayout = (key: string) => (event: LayoutChangeEvent) => {
    const { x, width } = event.nativeEvent.layout;
    setLayouts((previous) => (previous[key]?.x === x && previous[key]?.width === width ? previous : { ...previous, [key]: { x, width } }));
  };

  return (
    <View
      className="flex-row items-center justify-between border-t border-border bg-card px-4"
      style={[TAB_BAR_SHADOW, { paddingTop: TAB_TOP, paddingBottom: Math.max(insets.bottom, MIN_BOTTOM_INSET) }]}
      accessibilityRole="tablist"
    >
      <Animated.View style={[INDICATOR_BASE, indicatorStyle]} pointerEvents="none" accessible={false}>
        <View className="flex-1 rounded-lg bg-accent" />
      </Animated.View>
      {state.routes.map((route, index) => {
        const options = descriptors[route.key]?.options;
        const focused = state.index === index;
        const label = typeof options?.title === "string" ? options.title : route.name;
        const icon = TAB_ICONS[route.name] ?? House;

        const handlePress = () => {
          const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
          if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
        };

        return (
          <Pressable
            key={route.key}
            onPress={handlePress}
            onLayout={rememberLayout(route.key)}
            accessibilityRole="tab"
            accessibilityLabel={label}
            accessibilityState={{ selected: focused }}
            className={cn("h-12 min-w-touch items-center justify-center gap-1 rounded-lg px-3 py-1", !focused && "active:opacity-70")}
          >
            <Icon as={icon} size={20} className={focused ? "text-primary" : "text-card-foreground"} />
            <Text className={cn("text-caption", focused ? "text-primary" : "text-card-foreground")}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// 인디케이터는 탭 행과 같은 높이·세로 위치에 절대 배치하고 가로 자리만 움직인다
const INDICATOR_BASE = { position: "absolute", top: TAB_TOP, left: 0, height: TAB_HEIGHT } as const;

export { TabBar };
export type { TabBarProps };
