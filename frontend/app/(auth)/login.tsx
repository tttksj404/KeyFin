import { SafeAreaView } from "react-native-safe-area-context";

import { LoginScreen } from "@/features/auth/components/LoginScreen";

// PAGE-01 로그인. 온보딩 첫 화면이라 헤더도 탭바도 없다.
export default function LoginRoute() {
  return (
    <SafeAreaView className="flex-1 bg-background" edges={["top", "bottom"]}>
      <LoginScreen />
    </SafeAreaView>
  );
}
