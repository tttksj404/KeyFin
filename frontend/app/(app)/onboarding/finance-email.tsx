import { SafeAreaView } from "react-native-safe-area-context";

import { FinanceEmailScreen } from "@/features/link/components/FinanceEmailScreen";

// PAGE-03B 금융망 이메일 연결. 약관 동의 뒤, 계좌·카드 연결 앞에 온다.
export default function FinanceEmailRoute() {
  return (
    <SafeAreaView className="flex-1 bg-card" edges={["top", "bottom"]}>
      <FinanceEmailScreen />
    </SafeAreaView>
  );
}
