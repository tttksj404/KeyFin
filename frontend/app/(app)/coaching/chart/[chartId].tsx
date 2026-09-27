import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { CoachingChartScreen } from "@/features/coaching/components/CoachingChartScreen";
import { parseChartId } from "@/features/coaching/model";

// 예산 예측 차트 (P1, FR-AI-04 부속). 코칭 대화(PAGE-31)의 답변에 붙는 차트에서 들어온다 — 진입 계약은 TBD(2026-09-22).
export default function CoachingChartRoute() {
  const { chartId } = useLocalSearchParams();

  return (
    <View className="flex-1 bg-background">
      <CoachingChartScreen chartId={parseChartId(chartId)} />
    </View>
  );
}
