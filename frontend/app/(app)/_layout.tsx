import { Redirect, Stack, usePathname } from "expo-router";
import { View } from "react-native";

import { loginHref } from "@/features/auth/model";
import { selectAuthStatus, useAuthStore } from "@/features/auth/store";
import { usePushDeviceRegistration, usePushForegroundDisplay } from "@/features/notification/api/queries";
import { usePushDeepLink } from "@/features/notification/usePushDeepLink";

/**
 * 로그인이 필요한 화면 그룹. 인증 검사는 여기 한 곳에서만 한다 (규칙 80).
 * 괄호 그룹이라 주소는 그대로다 — `/transaction/501` · `myfirstapp://payment/transfer/501` 모두 바뀌지 않는다.
 *
 * 여기서는 로그인 여부만 본다. 약관·금융망 연결·온보딩 재개 판정은 탭 레이아웃이 이어서 하는데,
 * 온보딩 화면들도 이 그룹 안에 있어서 여기서 같이 검사하면 리다이렉트가 돈다.
 */
export default function AppLayout() {
  const status = useAuthStore(selectAuthStatus);
  const pathname = usePathname();
  // 로그인한 동안 이 기기를 푸시 대상으로 등록한다(FR-NTF-01). 로그인 직후·앱 재시작 모두 여기를 지난다.
  usePushDeviceRegistration(status === "authenticated");
  // 앱을 보고 있는 동안 온 푸시도 OS 배너로 띄우고 관련 화면을 새로 받는다 (FR-NTF-01).
  usePushForegroundDisplay(status === "authenticated");
  // 푸시를 탭하면 대상 화면으로 보낸다. 앱이 꺼져 있다 켜진 경우도 여기서 받는다 (FR-NTF-01).
  usePushDeepLink(status === "authenticated");

  // 저장된 세션을 읽는 동안 로그인 화면이 깜빡이지 않도록 빈 배경을 둔다.
  if (status === "loading") return <View className="flex-1 bg-background" />;
  // 푸시·딥링크로 바로 들어왔을 수 있어 로그인 뒤 돌아올 주소를 넘긴다.
  if (status === "anonymous") return <Redirect href={loginHref(pathname)} />;

  return <Stack screenOptions={{ headerShown: false }} />;
}
