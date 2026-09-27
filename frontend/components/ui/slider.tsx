import * as React from "react";
import { View, type GestureResponderEvent, type LayoutChangeEvent } from "react-native";

import { cn } from "@/lib/utils";

const KNOB_SIZE = 18;

type SliderProps = {
  value: number;
  max: number;
  min?: number;
  step?: number;
  onValueChange: (value: number) => void;
  disabled?: boolean;
  accessibilityLabel?: string;
  className?: string;
  /** 채움 막대와 손잡이 색. 봉투 행이면 `envelopeTone(id).bar`, 기본은 primary */
  fillClassName?: string;
};

/**
 * 손잡이 하나짜리 슬라이더. RN 코어 responder 이벤트만 써서 네이티브와 웹(Expo web)에서 같게 동작한다.
 * 트랙 어디를 눌러도 그 지점으로 값이 옮겨가고, 끄는 동안에는 손가락 위치를 따라간다.
 *
 * 손가락 위치는 `locationX` 가 아니라 `pageX` 로 읽는다(2026-09-22 사용자 보고).
 * `locationX` 는 처음 닿은 **가장 안쪽 뷰** 기준이라, 손잡이 위에서 끌기 시작하면 손잡이 왼쪽 끝이 원점이 된다.
 * 손잡이는 값에 따라 움직이므로 원점도 따라 움직여 값이 왔다 갔다 했다(드르륵). 웹에서는 포인터가 트랙 밖으로 나가면
 * `locationX` 가 NaN 이 되어 `BigInt(NaN)` 까지 터졌다. 그래서 자식들은 터치를 받지 않게 하고, 누르는 순간
 * `pageX - locationX` 로 트랙의 화면 위치를 잡아 둔 뒤 끄는 동안은 `pageX` 만 쓴다.
 */
function Slider({
  value,
  max,
  min = 0,
  step = 1,
  onValueChange,
  disabled = false,
  accessibilityLabel,
  className,
  fillClassName = "bg-primary",
}: SliderProps) {
  const [width, setWidth] = React.useState(0);
  /** 끄는 동안 고정해 두는 트랙 왼쪽 끝의 화면 x. 누르는 순간 잡고 떼면 비운다 */
  const trackPageX = React.useRef<number | null>(null);

  const snap = (raw: number) => Math.round(Math.min(max, Math.max(min, raw)) / step) * step;

  const localX = (event: GestureResponderEvent): number => {
    const { pageX, locationX } = event.nativeEvent;
    return trackPageX.current === null ? locationX : pageX - trackPageX.current;
  };

  const moveTo = (event: GestureResponderEvent) => {
    if (width <= 0) return;
    const x = localX(event);
    if (!Number.isFinite(x)) return;
    const next = snap(min + (x / width) * (max - min));
    if (Number.isFinite(next) && next !== value) onValueChange(next);
  };

  const grab = (event: GestureResponderEvent) => {
    const { pageX, locationX } = event.nativeEvent;
    trackPageX.current = Number.isFinite(pageX) && Number.isFinite(locationX) ? pageX - locationX : null;
    moveTo(event);
  };

  const release = () => {
    trackPageX.current = null;
  };

  const handleLayout = (event: LayoutChangeEvent) => {
    setWidth(event.nativeEvent.layout.width);
  };

  const ratio = max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0;
  const knobLeft = Math.min(Math.max(0, width - KNOB_SIZE), Math.max(0, ratio * width - KNOB_SIZE / 2));

  return (
    <View
      className={cn("h-5 w-full justify-center", disabled && "opacity-50", className)}
      onLayout={handleLayout}
      onStartShouldSetResponder={() => !disabled}
      onMoveShouldSetResponder={() => !disabled}
      onResponderGrant={grab}
      onResponderMove={moveTo}
      onResponderRelease={release}
      onResponderTerminate={release}
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled }}
      accessibilityValue={{ min, max, now: value }}
      accessibilityActions={[
        { name: "increment", label: "늘리기" },
        { name: "decrement", label: "줄이기" },
      ]}
      onAccessibilityAction={(event) => {
        if (disabled) return;
        onValueChange(snap(value + (event.nativeEvent.actionName === "increment" ? step : -step)));
      }}
    >
      {/* 채움 막대·손잡이는 터치를 받지 않는다 — 트랙이 항상 터치 대상이어야 locationX 원점이 트랙 왼쪽 끝이다 */}
      <View className="h-1.5 w-full overflow-hidden rounded-full bg-muted" pointerEvents="none">
        <View className={cn("h-full rounded-full", fillClassName)} style={{ width: `${ratio * 100}%` }} />
      </View>
      <View
        className={cn("absolute items-center justify-center rounded-full", fillClassName)}
        style={{ left: knobLeft, width: KNOB_SIZE, height: KNOB_SIZE }}
        pointerEvents="none"
      >
        <View className="h-1.5 w-1.5 rounded-full bg-primary-foreground" />
      </View>
    </View>
  );
}

export { Slider, KNOB_SIZE };
export type { SliderProps };
