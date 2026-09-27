import { SafeAreaView } from "react-native-safe-area-context";

import { SpendingSummaryScreen } from "@/features/budget/components/SpendingSummaryScreen";

// PAGE-06 소비 분석 결과 A(요약). 다음은 봉투별(B).
export default function SpendingSummaryRoute() {
  return (
    <SafeAreaView className="flex-1 bg-background" edges={["top"]}>
      <SpendingSummaryScreen />
    </SafeAreaView>
  );
}
