import { Redirect, useRouter } from "expo-router";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/components/ui/button";
import { CountUpAmount } from "@/components/ui/count-up-amount";
import { Separator } from "@/components/ui/separator";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useCachedBudgetProposal } from "@/features/budget/api/queries";
import { AnalysisHero, SpendingBarRow } from "@/features/budget/components/SpendingAnalysisParts";
import { monthlyAvgPercent, sortByMonthlyAvg, sumAmounts } from "@/features/budget/model";
import { currentMonthKey } from "@/lib/date";
import { formatKRW } from "@/lib/money";

const SUMMARY_ROUTE = "/onboarding/spending-summary";
const ANALYZING_ROUTE = "/onboarding/spending-analysis";
const PROPOSAL_ROUTE = "/onboarding/budget-proposal";

/** 하단 CTA 가 안전 영역이 없는 기기에서도 띄워지는 최소 여백 (AssetSelectScreen 과 같은 기준) */
const MIN_BOTTOM_INSET = 12;

/** 얇은 막대 7개가 위에서부터 차례로 차오른다(요약 A 의 3개보다 촘촘하게) */
const FILL_STAGGER_MS = 80;

// PAGE-06 소비 분석 결과 B (Pencil spending-analysis/envelopes t02uSx, 헤더 '카테고리별 소비 분석', 아이콘 타일 없음). 봉투 전체를 많이 쓴 순으로 보여 주고 합계를 단다.
// 제안은 분석 중 화면이 받아 둔 캐시만 읽고, 없으면(앱 재시작 등) 분석 중으로 돌려보낸다.
function SpendingEnvelopesScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const proposal = useCachedBudgetProposal(currentMonthKey());

  if (proposal.data === undefined) return <Redirect href={ANALYZING_ROUTE} />;

  const { envelopes } = proposal.data;
  const ranked = sortByMonthlyAvg(envelopes);
  const max = ranked[0]?.monthlyAvg ?? "0";
  const total = sumAmounts(envelopes.map((envelope) => envelope.monthlyAvg));

  return (
    <Screen>
      <ScreenHeader
      flat
        title="카테고리별 소비 분석"
        onBack={() => (router.canGoBack() ? router.back() : router.replace(SUMMARY_ROUTE))}
      />

      <ScreenScrollView className="flex-1" contentContainerClassName="gap-7 px-6 pb-6 pt-4">
        <AnalysisHero description="이 금액을 바탕으로 봉투별 한 달 예산을 제안해 드릴게요." />

        <View className="gap-3.5">
          <View className="flex-row items-center justify-between">
            <Text className="text-h3 text-foreground" accessibilityRole="header">
              봉투별 한 달 평균
            </Text>
            <Text className="text-caption tabular-nums text-card-foreground">{envelopes.length}개</Text>
          </View>
          {ranked.map((envelope, index) => (
            <SpendingBarRow
              key={envelope.envelopeId}
              envelopeId={envelope.envelopeId}
              name={envelope.name}
              value={formatKRW(envelope.monthlyAvg)}
              percent={monthlyAvgPercent(envelope.monthlyAvg, max)}
              thin
              fillDelay={index * FILL_STAGGER_MS}
            />
          ))}
        </View>

        <Separator />

        <View className="flex-row items-center justify-between">
          <Text className="text-label text-foreground">합계</Text>
          <CountUpAmount value={total} className="text-amount-md tabular-nums text-foreground" />
        </View>
      </ScreenScrollView>

      <View className="px-6 pt-3" style={{ paddingBottom: Math.max(insets.bottom, MIN_BOTTOM_INSET) }}>
        <Button size="lg" className="h-button-lg rounded-lg" onPress={() => router.push(PROPOSAL_ROUTE)}>
          <Text>예산 제안 보기</Text>
        </Button>
      </View>
    </Screen>
  );
}

export { SpendingEnvelopesScreen };
