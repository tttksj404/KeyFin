import * as React from "react";
import {
  FlatList,
  ScrollView,
  View,
  type FlatListProps,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  type ScrollViewProps,
} from "react-native";
import { useSharedValue, type SharedValue } from "react-native-reanimated";
import { SafeAreaInsetsContext } from "react-native-safe-area-context";

import { cn } from "@/lib/utils";

/** 헤더 바와 본문 사이 간격 (2026-09-16 사용자 결정) */
export const HEADER_CONTENT_GAP = 24;
/** 상태바 아래 헤더 제목 행 높이(`min-h-20`) + 하단 보더 1 */
export const HEADER_BAR_HEIGHT = 80 + 1;

/** 헤더가 없는 화면에서 본문이 상태바를 피하도록 두는 간격 (2026-09-18: 12 → 20, 자산·예산 탭이 너무 붙어 보인다는 사용자 요청) */
export const HEADERLESS_TOP_GAP = 20;

/** 헤더 전체 높이 = 상태바 영역 + 제목 행. 측정하지 않고 계산한다 — 측정에 기대면 첫 렌더에 본문이 헤더 아래로 들어간다 */
export function useHeaderHeight(): number {
  const insets = React.useContext(SafeAreaInsetsContext);
  return (insets?.top ?? 0) + HEADER_BAR_HEIGHT;
}

/**
 * 상태바 높이. `useSafeAreaInsets` 는 프로바이더가 없으면 던지므로(테스트) 컨텍스트를 직접 읽는다.
 */
export function useTopInset(): number {
  return React.useContext(SafeAreaInsetsContext)?.top ?? 0;
}

/**
 * 헤더 없는 화면(탭 화면)의 본문 위 여백 (2026-09-18 코치 피드백으로 탭 헤더 제거).
 * 탭바가 현재 위치를 알려 주므로 탭 화면에는 제목 헤더를 두지 않는다.
 * 뒤로가기가 있는 상세·온보딩 화면은 돌아갈 방법이 사라지므로 `ScreenHeader` 를 그대로 쓴다.
 */
export function useHeaderlessTop(): number {
  return useTopInset() + HEADERLESS_TOP_GAP;
}

type ScreenScrollContextValue = {
  /** 본문 스크롤 위치. 헤더가 이 값으로 투명해진다 */
  scrollY: SharedValue<number>;
};

const ScreenScrollContext = React.createContext<ScreenScrollContextValue | null>(null);

export function useScreenScroll(): ScreenScrollContextValue | null {
  return React.useContext(ScreenScrollContext);
}

type ScreenProps = {
  children: React.ReactNode;
  className?: string;
};

/**
 * 헤더가 본문 위에 겹치는 화면의 뿌리. 안에 `ScreenHeader` 와 `ScreenScrollView`/`ScreenFlatList` 를 둔다.
 * 헤더는 절대 위치로 위에 떠 있고(상태바 영역까지 흰 면), 스크롤하면 투명해져 내용이 그 아래로 지나간다.
 * 헤더 자리는 `ScreenHeader` 가 같은 높이의 빈 공간을 흐름에 남겨 채우므로, 스크롤이 없는 상태(스켈레톤·빈 화면)도 헤더 아래에서 시작한다.
 */
function Screen({ children, className }: ScreenProps) {
  const scrollY = useSharedValue(0);
  const value = React.useMemo(() => ({ scrollY }), [scrollY]);

  return (
    <ScreenScrollContext.Provider value={value}>
      <View className={cn("flex-1 bg-background", className)}>{children}</View>
    </ScreenScrollContext.Provider>
  );
}

type OverlapOption = {
  /**
   * 목록이 헤더 밑으로 지나가며 헤더가 투명해진다(기본). 헤더와 목록 사이에 월 선택·필터 같은 고정 컨트롤이 있으면 false —
   * 끌어올린 목록이 그 컨트롤을 덮어 누를 수 없게 되므로, 목록은 컨트롤 아래에서만 스크롤되고 헤더도 그대로 둔다.
   */
  overlapHeader?: boolean;
};

function useScrollTracking(onScroll: ((event: NativeSyntheticEvent<NativeScrollEvent>) => void) | undefined, overlapHeader: boolean) {
  const context = useScreenScroll();
  const headerHeight = useHeaderHeight();
  const scrollY = overlapHeader ? context?.scrollY : undefined;
  const handleScroll = React.useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      scrollY?.set(event.nativeEvent.contentOffset.y);
      onScroll?.(event);
    },
    [scrollY, onScroll]
  );
  const overlaid = context !== null && overlapHeader;
  // 헤더 자리(빈 공간)만큼 위로 끌어올리고 내용은 그만큼 내려서, 쉬는 상태 배치는 그대로 두고 스크롤만 헤더 아래로 이어지게 한다
  const offset = overlaid ? headerHeight + HEADER_CONTENT_GAP : 0;
  return { handleScroll, offset, overlaid };
}

/** `Screen` 안에서 쓰는 ScrollView. 밖에서 쓰면 보통 ScrollView 와 같다 */
function ScreenScrollView({ onScroll, contentContainerStyle, overlapHeader = true, ...props }: ScrollViewProps & OverlapOption) {
  const { handleScroll, offset, overlaid } = useScrollTracking(onScroll, overlapHeader);
  const scroll = (
    <ScrollView
      {...props}
      onScroll={handleScroll}
      scrollEventThrottle={16}
      contentContainerStyle={[contentContainerStyle, overlaid ? { paddingTop: offset } : null]}
    />
  );
  return overlaid ? <PulledUp offset={offset}>{scroll}</PulledUp> : scroll;
}

/**
 * `Screen` 안에서 쓰는 FlatList. 밖에서 쓰면 보통 FlatList 와 같다.
 * 위 여백은 contentContainerStyle 이 아니라 목록 머리의 빈 View 로 넣는다 — NativeWind 가 FlatList 의 contentContainerClassName 을
 * remapProps 로 처리해 웹에서 인라인 contentContainerStyle 을 덮어써, 여백이 빠지고 내용이 헤더 밑에 깔렸다 (2026-09-17).
 */
function ScreenFlatList<ItemT>({
  onScroll,
  style,
  ListHeaderComponent,
  overlapHeader = true,
  ref,
  ...props
}: FlatListProps<ItemT> & OverlapOption & { ref?: React.Ref<FlatList<ItemT>> }) {
  const { handleScroll, offset, overlaid } = useScrollTracking(onScroll, overlapHeader);
  const header = overlaid ? (
    <View>
      <View style={{ height: offset }} />
      {renderListHeader(ListHeaderComponent)}
    </View>
  ) : (
    ListHeaderComponent
  );
  // 코칭 대화처럼 새 줄이 붙을 때 끝으로 스크롤하려면 목록 ref 가 필요하다(React 19 는 ref 를 보통 prop 으로 받는다).
  const list = <FlatList {...props} ref={ref} style={style} ListHeaderComponent={header} onScroll={handleScroll} scrollEventThrottle={16} />;
  return overlaid ? <PulledUp offset={offset}>{list}</PulledUp> : list;
}

/**
 * 헤더 자리만큼 위로 끌어올리는 래퍼. 여백을 스크롤 컴포넌트의 style 에 주지 않는 이유: 당겨서 새로고침(refreshControl)이 붙으면
 * 웹(RN Web)은 스크롤 뷰를 바깥 래퍼로 감싸면서 같은 style 을 바깥·안쪽 양쪽에 적용해 -offset 이 두 번 먹는다 —
 * 봉투 상세가 헤더 밑에 깔린 원인이었다 (2026-09-17 웹에서 측정: 바깥 top 0 · 안쪽 top -105).
 */
function PulledUp({ offset, children }: { offset: number; children: React.ReactNode }) {
  return <View style={{ flex: 1, marginTop: -offset }}>{children}</View>;
}

function renderListHeader(header: FlatListProps<unknown>["ListHeaderComponent"]): React.ReactNode {
  if (header === null || header === undefined) return null;
  if (React.isValidElement(header)) return header;
  return React.createElement(header as React.ComponentType);
}

export { Screen, ScreenFlatList, ScreenScrollView };
