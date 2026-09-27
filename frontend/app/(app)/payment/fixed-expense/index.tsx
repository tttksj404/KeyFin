import { View } from "react-native";

import { FixedExpenseListScreen } from "@/features/payment/components/FixedExpenseListScreen";

// 고정지출 관리(PAGE-26B). 결제 캘린더 헤더의 '관리'에서 들어온다. 항목을 누르면 수정(PAGE-26), + 는 등록.
export default function FixedExpenseListRoute() {
  return (
    <View className="flex-1 bg-background">
      <FixedExpenseListScreen />
    </View>
  );
}
