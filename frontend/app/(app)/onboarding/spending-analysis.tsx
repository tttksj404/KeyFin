import { SafeAreaView } from "react-native-safe-area-context";

import { SpendingAnalyzingScreen } from "@/features/budget/components/SpendingAnalyzingScreen";

// PAGE-06 분석 중. 수입 계좌 지정(PAGE-05) 뒤에 오고, 결과에 따라 소비 분석 결과(A) 또는 예산 제안(PAGE-07)으로 넘어간다.
export default function SpendingAnalyzingRoute() {
  return (
    <SafeAreaView className="flex-1 bg-background" edges={["top"]}>
      <SpendingAnalyzingScreen />
    </SafeAreaView>
  );
}
