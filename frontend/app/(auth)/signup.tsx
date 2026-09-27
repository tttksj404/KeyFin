import { SafeAreaView } from "react-native-safe-area-context";

import { SignupScreen } from "@/features/auth/components/SignupScreen";

// PAGE-02 회원가입. 로그인에서 들어오므로 뒤로가기가 있다.
export default function SignupRoute() {
  return (
    <SafeAreaView className="flex-1 bg-card" edges={["top", "bottom"]}>
      <SignupScreen />
    </SafeAreaView>
  );
}
