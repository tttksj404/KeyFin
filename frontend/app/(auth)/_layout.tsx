import { Redirect, Stack, useLocalSearchParams } from "expo-router";

import { parseReturnTo } from "@/features/auth/model";
import { selectAuthStatus, selectTermsAgreed, useAuthStore } from "@/features/auth/store";
import { useFinanceStatus } from "@/features/link/api/queries";

// 인증 화면 그룹. 이미 로그인된 사용자는 홈으로 돌려보낸다 (규칙 80: 인증 검사는 그룹 레이아웃에서).
// 단 약관(PAGE-03)은 로그인한 뒤에 보는 화면이라 미동의 상태에서는 그대로 둔다.
export default function AuthLayout() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const status = useAuthStore(selectAuthStatus);
  const termsAgreed = useAuthStore(selectTermsAgreed);
  const financeStatus = useFinanceStatus();

  // 약관·금융망 연결이 남아 있으면 홈으로 보내지 않는다. 각 화면이 다음 단계를 이어서 안내한다.
  if (status === "authenticated" && termsAgreed !== false && financeStatus.data !== false) {
    return <Redirect href={parseReturnTo(returnTo)} />;
  }
  return <Stack screenOptions={{ headerShown: false }} />;
}
