import { Redirect, useRouter } from "expo-router";
import { ChartPie } from "lucide-react-native";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/components/ui/button";
import { CountUpAmount } from "@/components/ui/count-up-amount";
import { Text } from "@/components/ui/text";
import { useCachedBudgetProposal } from "@/features/budget/api/queries";
import { AnalysisHero, SpendingBarRow } from "@/features/budget/components/SpendingAnalysisParts";
import { monthlyAvgPercent, sortByMonthlyAvg, sumAmounts } from "@/features/budget/model";
import { currentMonthKey } from "@/lib/date";
import { formatKRW } from "@/lib/money";

const ENVELOPES_ROUTE = "/onboarding/spending-envelopes";
const ANALYZING_ROUTE = "/onboarding/spending-analysis";

const TOP_SPENDING_COUNT = 3;

/** 막대 3개가 위에서부터 차례로 차오른다 */
const FILL_STAGGER_MS = 150;

/** 하단 CTA 가 안전 영역이 없는 기기에서도 띄워지는 최소 여백 (AssetSelectScreen 과 같은 기준) */
const MIN_BOTTOM_INSET = 12;

// PAGE-06 소비 분석 결과 A (Pencil spending-analysis/summary mhzUD). 한 달 평균 합계와 가장 많이 쓴 봉투 3개.
// 제안은 분석 중 화면이 받아 둔 캐시만 읽고, 없으면(앱 재시작 등) 분석 중으로 돌려보낸다.
function SpendingSummaryScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const proposal = useCachedBudgetProposal(currentMonthKey());

  if (proposal.data === undefined) return <Redirect href={ANALYZING_ROUTE} />;

  const { basis, envelopes } = proposal.data;
  const ranked = sortByMonthlyAvg(envelopes);
  const max = ranked[0]?.monthlyAvg ?? "0";
  const total = sumAmounts(envelopes.map((envelope) => envelope.monthlyAvg));

  return (
    <View className="flex-1 bg-background">
      <ScrollView className="flex-1" contentContainerClassName="gap-9 px-6 pb-6 pt-10">
        <AnalysisHero icon={ChartPie} title="지난 소비를 분석했어요" description={`${basis} 기준으로 계산했어요.`} />

        {/* 한 달 평균 소비는 흰 카드로 감싼다 (2026-09-17 사용자 요청, Pencil mhzUD Summary 도 같이 바꿈) */}
        <View className="gap-1 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
          <Text className="text-label text-card-foreground">한 달 평균 소비</Text>
          <CountUpAmount value={total} className="text-amount-lg tabular-nums text-foreground" />
        </View>

        <View className="gap-4">
          <Text className="text-h3 text-foreground" accessibilityRole="header">
            가장 많이 쓴 곳
          </Text>
          {ranked.slice(0, TOP_SPENDING_COUNT).map((envelope, index) => (
            <SpendingBarRow
              key={envelope.envelopeId}
              envelopeId={envelope.envelopeId}
              name={envelope.name}
              value={`월 ${formatKRW(envelope.monthlyAvg)}`}
              percent={monthlyAvgPercent(envelope.monthlyAvg, max)}
              fillDelay={index * FILL_STAGGER_MS}
            />
          ))}
        </View>
      </ScrollView>

      <View className="px-6 pt-3" style={{ paddingBottom: Math.max(insets.bottom, MIN_BOTTOM_INSET) }}>
        <Button size="lg" className="h-button-lg rounded-lg" onPress={() => router.push(ENVELOPES_ROUTE)}>
          <Text>다음</Text>
        </Button>
      </View>
    </View>
  );
}

export { SpendingSummaryScreen };
