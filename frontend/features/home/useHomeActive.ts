import { useFocusEffect } from "expo-router";
import * as React from "react";
import { AppState } from "react-native";

/** 홈 탭이 선택되어 있고 앱도 화면에 보일 때만 말풍선을 표시한다. */
export function useHomeActive(): boolean {
  const [focused, setFocused] = React.useState(false);
  const [foreground, setForeground] = React.useState(() => AppState.currentState === "active");

  useFocusEffect(
    React.useCallback(() => {
      setFocused(true);
      return () => setFocused(false);
    }, [])
  );

  React.useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => setForeground(state === "active"));
    // 구독 전 상태가 바뀌었어도 최초 상태를 그대로 쓰지 않는다.
    setForeground(AppState.currentState === "active");
    return () => subscription.remove();
  }, []);

  return focused && foreground;
}
