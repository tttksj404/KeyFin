import * as React from "react";
import { Modal, Pressable, View, type LayoutChangeEvent } from "react-native";
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";

import { KeyboardAvoidingView } from "@/components/ui/keyboard-avoiding-view";

/** 뒤 화면이 어두워지는(밝아지는) 시간이자 시트가 오르내리는 시간 (2026-09-16 사용자 요청) */
const SHEET_MS = 280;
const SCRIM_FILL = { position: "absolute", top: 0, right: 0, bottom: 0, left: 0 } as const;

type BottomSheetProps = {
  visible: boolean;
  onClose: () => void;
  /** 스크림(어두운 영역)을 눌러 닫을 때의 접근성 라벨 — "예산 보드 닫기" 처럼 무엇을 닫는지 적는다 */
  closeLabel: string;
  /** 시트 최대 높이(픽셀). 없으면 내용 높이 */
  maxHeight?: number;
  children: React.ReactNode;
};

/**
 * 아래서 올라오는 시트. RN Modal 위에 스크림과 시트를 따로 움직인다 —
 * 열릴 때 뒤 화면이 서서히 어두워지며 시트만 올라오고, 닫힐 때는 반대로 시트가 내려가며 밝아진다.
 * RN Modal 은 `visible` 이 꺼지면 바로 사라져 닫힘 애니메이션이 안 보이므로, 시트가 다 내려간 뒤에 모달을 내린다.
 * 홈 예산 시트·세분류 시트·거래 필터 선택창이 쓴다 (DESIGN.md 인벤토리 BottomSheet).
 *
 * 움직임은 Reanimated 레이아웃 애니메이션(entering/exiting)이 아니라 진행값(0~1) 하나로 만든 transform 이다.
 * entering 으로 올린 시트는 Android 실기기에서 첫 탭이 먹지 않아 시트 안 항목을 두 번 눌러야 했다
 * (상점 종류 선택·홈 예산 시트의 예산 탭 링크, 2026-09-22). transform 은 네이티브 뷰에 그대로 걸려 터치 자리가 어긋나지 않는다.
 */
function BottomSheet({ visible, onClose, closeLabel, maxHeight, children }: BottomSheetProps) {
  // 모달은 시트가 다 내려간 뒤에 내린다. visible 이 바뀐 순간을 렌더 중에 잡아 두는 패턴(이전 렌더 값 기억)이라 effect 가 없다.
  // 내려가는 동안에는 닫히던 순간의 내용을 그대로 보여 준다 — 닫히면서 단계를 되돌리는 시트(세분류)가 내려가다 말고 바뀌어 보이지 않게.
  const [lag, setLag] = React.useState<{ mounted: boolean; seenVisible: boolean; closingChildren: React.ReactNode }>({
    mounted: visible,
    seenVisible: visible,
    closingChildren: null,
  });
  if (lag.seenVisible !== visible) {
    setLag({ mounted: visible || lag.mounted, seenVisible: visible, closingChildren: visible ? null : children });
  }
  const mounted = visible || lag.mounted;

  /** 0 = 다 내려감(스크림 투명), 1 = 다 올라옴 */
  const progress = useSharedValue(0);
  /** 시트 높이. 재기 전(0)에는 내릴 거리를 몰라 시트를 숨겨 둔다 */
  const sheetHeight = useSharedValue(0);

  // 내려가는 동안 다시 열렸으면(seenVisible 이 참) 모달을 내리지 않는다
  const finishClose = React.useCallback(
    () => setLag((state) => (state.seenVisible || !state.mounted ? state : { ...state, mounted: false, closingChildren: null })),
    []
  );

  // 애니메이션이라는 바깥 시스템을 visible 에 맞춘다 (규칙 10). 여는 쪽은 높이를 잰 뒤(handleLayout)에 시작한다.
  React.useEffect(() => {
    if (visible) {
      if (sheetHeight.get() > 0) progress.set(withTiming(1, { duration: SHEET_MS }));
      return;
    }
    progress.set(
      withTiming(0, { duration: SHEET_MS }, (finished) => {
        "worklet";
        if (finished) runOnJS(finishClose)();
      })
    );
  }, [visible, progress, sheetHeight, finishClose]);

  const handleLayout = (event: LayoutChangeEvent) => {
    sheetHeight.set(event.nativeEvent.layout.height);
    if (visible) progress.set(withTiming(1, { duration: SHEET_MS }));
  };

  const scrimStyle = useAnimatedStyle(() => ({ opacity: progress.value }));
  const sheetStyle = useAnimatedStyle(() => ({
    opacity: sheetHeight.value > 0 ? 1 : 0,
    transform: [{ translateY: (1 - progress.value) * sheetHeight.value }],
  }));

  return (
    <Modal visible={mounted} transparent animationType="none" onRequestClose={onClose}>
      {/* 시트 안 입력(세분류 시트의 더치페이 금액)에 키패드가 뜨면 시트째 밀어 올린다 — Modal 은 창이 줄지 않는다 */}
      <KeyboardAvoidingView className="flex-1 justify-end">
        <Animated.View style={[SCRIM_FILL, scrimStyle]} pointerEvents={visible ? "auto" : "none"}>
          <Pressable className="flex-1 bg-black/50" accessibilityRole="button" accessibilityLabel={closeLabel} onPress={onClose} />
        </Animated.View>
        {mounted ? (
          <Animated.View style={sheetStyle} onLayout={handleLayout} pointerEvents={visible ? "auto" : "none"}>
            <View className="rounded-t-xl bg-popover pb-8" style={maxHeight === undefined ? undefined : { maxHeight }}>
              {visible ? children : lag.closingChildren}
            </View>
          </Animated.View>
        ) : null}
      </KeyboardAvoidingView>
    </Modal>
  );
}

export { BottomSheet };
export type { BottomSheetProps };
