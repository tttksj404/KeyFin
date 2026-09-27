import { useRouter } from "expo-router";
import { SearchX, WifiOff } from "lucide-react-native";
import * as React from "react";
import { View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Screen } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useChartHtml } from "@/features/coaching/api/queries";
import { ChartHtmlView } from "@/features/coaching/components/ChartHtmlView";
import { chartErrorMessage, isChartNotFoundError } from "@/features/coaching/errors";

const CHAT_ROUTE = "/coaching/chat";
export const CHART_TITLE = "예산 예측";

type CoachingChartScreenProps = {
  /** 라우트 파라미터를 검증한 차트 id. 모양이 아니면 null → 못 찾음 */
  chartId: string | null;
};

/**
 * 예산 예측 차트 (PAGE-31 코칭 대화에서 연다 — 답변에 차트가 붙는 계약은 TBD, 2026-09-22 HTML 로 받기로만 결정).
 * 백엔드가 중계한 자기완결 HTML 을 화면 가득 WebView 로 그린다. 말풍선 안에 넣지 않는 이유: 목록 안에서 높이를 못 잡고
 * 차트의 select·hover 터치가 목록 스크롤과 겹친다. HTML 은 라이트 전용·시스템 글꼴이라 바탕만 카드색으로 고정한다.
 * Pencil 미대조(시안 없음).
 */
function CoachingChartScreen({ chartId }: CoachingChartScreenProps) {
  const router = useRouter();
  const chart = useChartHtml(chartId);
  // WebView 가 문서 자체를 못 그린 경우(onError). 받은 HTML 은 캐시에 있으니 다시 시도는 다시 그리기다
  const [renderFailed, setRenderFailed] = React.useState(false);

  const goBack = () => (router.canGoBack() ? router.back() : router.replace(CHAT_ROUTE));
  const notFound = chartId === null || isChartNotFoundError(chart.error);
  const retry = () => {
    setRenderFailed(false);
    if (chart.isError) void chart.refetch();
  };

  return (
    <Screen>
      <ScreenHeader title={CHART_TITLE} onBack={goBack} />
      {notFound ? (
        <CenteredState>
          <EmptyState
            icon={SearchX}
            title="차트를 찾을 수 없어요"
            description="만료됐거나 다른 계정의 차트예요."
            action={{ label: "대화로 돌아가기", onPress: goBack }}
          />
        </CenteredState>
      ) : chart.isPending ? (
        <ChartSkeleton />
      ) : chart.isError || renderFailed ? (
        <CenteredState>
          <EmptyState
            icon={WifiOff}
            title="차트를 불러오지 못했어요"
            description={chart.isError ? chartErrorMessage(chart.error) : undefined}
            action={{ label: "다시 시도", onPress: retry, disabled: chart.isFetching }}
          />
        </CenteredState>
      ) : (
        <View className="flex-1 bg-card">
          <ChartHtmlView html={chart.data} onLoadError={() => setRenderFailed(true)} />
        </View>
      )}
    </Screen>
  );
}

function CenteredState({ children }: { children: React.ReactNode }) {
  return <View className="flex-1 justify-center pb-20">{children}</View>;
}

/** 실제 차트 페이지 구성(제목·기간 태그·사용률 막대 7줄·추이 카드)을 따라 자리만 잡는다 */
function ChartSkeleton() {
  return (
    <View className="flex-1 gap-3 px-6" accessibilityLabel="차트를 불러오는 중">
      <Skeleton className="h-7 w-40 rounded-sm" />
      <Skeleton className="h-8 w-56 rounded-lg" />
      <View className="gap-2.5 pt-4">
        {[0, 1, 2, 3, 4, 5, 6].map((row) => (
          <Skeleton key={row} className="h-4 w-full rounded-full" />
        ))}
      </View>
      <Skeleton className="mt-4 h-64 w-full rounded-2xl" />
    </View>
  );
}

export { CoachingChartScreen };
