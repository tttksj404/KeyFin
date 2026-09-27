import { Redirect, Tabs } from "expo-router";
import { View } from "react-native";

import { TabBar } from "@/components/ui/tab-bar";
import { selectOnboardingDone, selectTermsAgreed, useAuthStore } from "@/features/auth/store";
import { useFinanceStatus } from "@/features/link/api/queries";
import { usePushPermissionPrompt } from "@/features/notification/api/queries";

// Pencil 홈 BottomTabBar (NaYk9): 홈 · 자산 · 예산 · 마이 — 리포트 탭은 구현하지 않기로 해 뺐다(사용자 결정 2026-09-23)
export default function TabsLayout() {
  const termsAgreed = useAuthStore(selectTermsAgreed);
  const onboardingDone = useAuthStore(selectOnboardingDone);
  const financeStatus = useFinanceStatus();
  // 아래 게이트를 통과해 탭이 보일 때만 알림 권한을 묻는다 — 온보딩 중에는 시스템 창을 띄우지 않는다.
  usePushPermissionPrompt(termsAgreed !== false && (onboardingDone === true || financeStatus.data === true));

  // 로그인 여부는 상위 (app) 그룹이 검사한다. 여기서는 온보딩 단계만 본다.
  if (termsAgreed === false) return <Redirect href="/(auth)/terms" />;
  // 온보딩을 마친 기록(첫 예산 확정)이 있으면 금융망 조회 결과와 무관하게 홈으로 — 서버 판정이 생기면 그걸로 바꾼다 (2026-09-16).
  if (onboardingDone !== true) {
    // 금융망 연결 여부는 서버가 가진 값이라 조회가 끝날 때까지 기다린다 (GET /links/status).
    if (financeStatus.isPending) return <View className="flex-1 bg-background" />;
    // 조회에 실패해도 연결이 확인되지 않았으니 홈이 아니라 금융망 이메일로 보낸다(사용자 결정 2026-09-17). 연결된 계정은 그 화면에서 다시 연결해도 멱등이다.
    if (financeStatus.data !== true) return <Redirect href="/onboarding/finance-email" />;
  }

  return (
    <Tabs screenOptions={{ headerShown: false }} tabBar={(props) => <TabBar {...props} />}>
      <Tabs.Screen name="index" options={{ title: "홈" }} />
      <Tabs.Screen name="assets" options={{ title: "자산" }} />
      <Tabs.Screen name="budget" options={{ title: "예산" }} />
      <Tabs.Screen name="my" options={{ title: "마이" }} />
    </Tabs>
  );
}
