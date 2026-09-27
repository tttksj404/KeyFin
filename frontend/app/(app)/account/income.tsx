import { View } from "react-native";

import { IncomeAccountScreen } from "@/features/account/components/IncomeAccountScreen";

// 수입 계좌 변경. 자산 탭(PAGE-11)의 '수입 계좌 변경'과 이체 승인의 PAY_010 오류에서 들어온다. 온보딩(PAGE-05)과 같은 화면의 변경 모드다.
export default function IncomeAccountChangeRoute() {
  return (
    <View className="flex-1 bg-background">
      <IncomeAccountScreen mode="change" />
    </View>
  );
}
