import { Stack, useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { EnvelopeDetailScreen } from "@/features/budget/components/EnvelopeDetailScreen";
import { parseEnvelopeId } from "@/features/budget/model";

// PAGE-23 봉투 상세. 홈 예산 카드의 봉투 막대와 BUDGET_ALERT 푸시(refId=envelopeId)에서 들어온다.
export default function EnvelopeDetailRoute() {
  const { envelopeId, from } = useLocalSearchParams();

  return (
    <View className="flex-1 bg-background">
      {/* 예산 탭의 봉투가 펼쳐져 화면을 덮은 채 들어오면 전환을 끈다 — 봉투 안에서 나온 것처럼 이어진다 (프로토타입 2026-09-19) */}
      <Stack.Screen options={{ animation: from === "envelope" ? "none" : "default" }} />
      <EnvelopeDetailScreen envelopeId={parseEnvelopeId(envelopeId)} />
    </View>
  );
}
