import { focusManager, QueryClient } from "@tanstack/react-query";
import { AppState, Platform } from "react-native";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

// 네이티브에는 창 포커스 이벤트가 없어 앱이 백그라운드에서 돌아와도 오래된 조회가 그대로 남는다 —
// 앱이 꺼져 있는 동안 온 푸시(코인 지급·새 거래)는 포그라운드 리스너도 못 받는다. 앱 상태를 포커스로 알려 돌아올 때 다시 받게 한다 (2026-09-22).
// 웹은 TanStack Query 기본 리스너(visibilitychange)를 그대로 쓴다.
if (Platform.OS !== "web") {
  focusManager.setEventListener((handleFocus) => {
    const subscription = AppState.addEventListener("change", (state) => handleFocus(state === "active"));
    return () => subscription.remove();
  });
}
