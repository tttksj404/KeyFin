import { View } from "react-native";

import { BudgetProposalScreen } from "@/features/budget/components/BudgetProposalScreen";

// PAGE-07 예산 제안·승인. 헤더가 안전 영역까지 bg-card 로 이어지도록 배경을 카드 색으로 둔다 (예산 탭과 같은 방식).
// 하단 안전 영역은 CTA 가 직접 띄운다 — 배경색이 다르기 때문이다.
export default function BudgetProposalRoute() {
  return (
    <View className="flex-1 bg-background">
      <BudgetProposalScreen />
    </View>
  );
}
