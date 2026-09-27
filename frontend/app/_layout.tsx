import "../global.css";

import { PortalHost } from "@rn-primitives/portal";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { Platform } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useSessionBootstrap } from "@/features/auth/useSessionBootstrap";
import { queryClient } from "@/lib/query-client";

// GestureHandlerRootView 는 NativeWind className 대상이 아니라 style 로 채운다.
const FILL = { flex: 1 } as const;

/**
 * 웹(개발 중 확인용)에는 상태 표시줄이 없어 헤더가 창 맨 위에 붙는다. 폰과 비슷하게 보이도록
 * 상단 안전 영역을 44 로 가장한다 — 띠를 따로 그리지 않고 안전 영역 값으로 주어야 헤더가 그 높이까지 칠하고 스크롤에 같이 투명해진다.
 * 기기에서는 expo-router 가 준 실제 값을 그대로 쓴다.
 */
const WEB_STATUS_BAR_HEIGHT = 44;
const WEB_SAFE_AREA = {
  frame: { x: 0, y: 0, width: 0, height: 0 },
  insets: { top: WEB_STATUS_BAR_HEIGHT, right: 0, bottom: 0, left: 0 },
} as const;

export default function RootLayout() {
  useSessionBootstrap();

  return (
    <GestureHandlerRootView style={FILL}>
      <QueryClientProvider client={queryClient}>
        {Platform.OS === "web" ? (
          <SafeAreaProvider initialMetrics={WEB_SAFE_AREA}>
            <Stack screenOptions={{ headerShown: false }} />
          </SafeAreaProvider>
        ) : (
          <Stack screenOptions={{ headerShown: false }} />
        )}
        <PortalHost />
        <StatusBar style="auto" />
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
