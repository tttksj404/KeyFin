import { Check } from "lucide-react-native";
import * as React from "react";
import { Pressable, View } from "react-native";
import Animated, { useAnimatedStyle, useReducedMotion, withTiming } from "react-native-reanimated";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

/** Pencil Switch / on·off (WGeTO·UgUeI): 트랙 48×28 둥근 알약, 좌우 안쪽 3, 흰 손잡이 22 */
const TRACK_PADDING = 3;
const THUMB_SIZE = 22;
const TRACK_WIDTH = 48;
const THUMB_TRAVEL = TRACK_WIDTH - THUMB_SIZE - TRACK_PADDING * 2;
const TOGGLE_MS = 160;
/** 켜짐 손잡이 안의 체크 */
const CHECK_SIZE = 14;
// 4px 스케일 밖 시안 치수라 크기·안쪽 여백만 style 로 준다
const TRACK_STYLE = { paddingHorizontal: TRACK_PADDING } as const;
const THUMB_STYLE = { width: THUMB_SIZE, height: THUMB_SIZE } as const;

type SwitchProps = {
  value: boolean;
  onValueChange: (value: boolean) => void;
  accessibilityLabel: string;
  disabled?: boolean;
  className?: string;
};

/**
 * 켜고 끄는 스위치. RN 코어 Switch 는 플랫폼마다 크기·모양이 고정돼(웹 40×20, 켜짐 손잡이 청록) 시안과 맞출 수 없어 직접 그린다 (2026-09-17).
 * 켜짐 = primary 트랙 + 손잡이 안 체크, 꺼짐 = input(회색) 트랙, 손잡이는 흰색에 그림자. 동작 줄이기 설정이면 손잡이가 바로 옮겨 간다.
 *
 * 2026-09-22 사용자 보고: 폰에서 흰 카드 위의 스위치가 버튼인지 바탕인지 헷갈렸다 — 꺼짐 트랙이 muted(#EAE8F5)라 흰 카드·흰 손잡이와
 * 거의 구분되지 않았고, 켜짐도 손잡이 오른쪽 여백이 3 뿐이라 파란 면이 작게 보였다. 그래서 꺼짐 트랙을 input 색으로 진하게 하고,
 * 손잡이에 그림자를 주고, 켜짐이면 손잡이 안에 체크를 그려 상태가 색에만 기대지 않게 한다.
 */
function Switch({ value, onValueChange, accessibilityLabel, disabled = false, className }: SwitchProps) {
  const reducedMotion = useReducedMotion();
  const thumbStyle = useAnimatedStyle(() => {
    const target = value ? THUMB_TRAVEL : 0;
    return { transform: [{ translateX: reducedMotion ? target : withTiming(target, { duration: TOGGLE_MS }) }] };
  }, [value, reducedMotion]);

  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ checked: value, disabled }}
      aria-checked={value}
      disabled={disabled}
      hitSlop={8}
      onPress={() => onValueChange(!value)}
      className={cn("h-7 w-12 justify-center rounded-full", value ? "bg-primary" : "bg-input", disabled && "opacity-50", className)}
      style={TRACK_STYLE}
    >
      <Animated.View style={[THUMB_STYLE, thumbStyle]}>
        <View className="flex-1 items-center justify-center rounded-full bg-white shadow-sm shadow-black/25">
          {value ? <Icon as={Check} size={CHECK_SIZE} strokeWidth={3} className="text-primary" /> : null}
        </View>
      </Animated.View>
    </Pressable>
  );
}

export { Switch };
export type { SwitchProps };
