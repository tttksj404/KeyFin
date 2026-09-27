import { SafeAreaView } from "react-native-safe-area-context";

import { TermsScreen } from "@/features/auth/components/TermsScreen";

// PAGE-03 약관 동의. 로그인 직후 미동의 상태면 (tabs) 레이아웃이 이리로 보낸다.
export default function TermsRoute() {
  return (
    <SafeAreaView className="flex-1 bg-card" edges={["top", "bottom"]}>
      <TermsScreen />
    </SafeAreaView>
  );
}
