import { Redirect } from "expo-router";
import { CircleAlert } from "lucide-react-native";
import * as React from "react";
import { View } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { LottieLoop } from "@/components/ui/lottie-loop";
import { Text } from "@/components/ui/text";
import { useBudgetProposal } from "@/features/budget/api/queries";
import { isBudgetExistsError, proposalErrorMessage } from "@/features/budget/errors";
import { hasSpendingHistory } from "@/features/budget/model";
import { currentMonthKey } from "@/lib/date";

/** 모래시계가 뒤집히는 로딩 애니메이션(LottieFiles "Time Hourglass", 색은 primary 계열로 바꿈, 1초 반복). 시안(pWPd0)의 아이콘 타일 자리 */
const ANALYZING_HOURGLASS = require("@/assets/lottie/analyzing-hourglass.json");
const HOURGLASS_STYLE = { width: 96, height: 96 } as const;

const SUMMARY_ROUTE = "/onboarding/spending-summary";

/** 소비 이력이 없으면 서버가 기본 예산으로 제안하므로 분석 결과(A·B)를 건너뛴다 (2026-09-11 BUDGET 백엔드와 합의) */
const PROPOSAL_ROUTE = "/onboarding/budget-proposal";

/** 하단 CTA 가 안전 영역이 없는 기기에서도 띄워지는 최소 여백 (AssetSelectScreen 과 같은 기준) */
const MIN_BOTTOM_INSET = 12;

// PAGE-06 분석 중. 예산 제안(POST /budgets/proposals)은 온보딩에서 여기서만 만들고,
// 결과는 캐시에 남아 소비 분석 결과(A·B)와 예산 제안(PAGE-07)이 이어서 쓴다.
function SpendingAnalyzingScreen() {
  const proposal = useBudgetProposal(currentMonthKey());

  if (proposal.data !== undefined) {
    return <Redirect href={hasSpendingHistory(proposal.data) ? SUMMARY_ROUTE : PROPOSAL_ROUTE} />;
  }
  // 이번 주기 예산이 이미 있으면(앱을 다시 켜 온보딩을 이어 가는 경우 등) 제안을 다시 만들 수 없다.
  // 예산 확정 화면이 GET /budgets/current 로 이미 있는 제안을 받으므로 분석 결과(A·B) 없이 그리로 보낸다.
  if (proposal.isError && isBudgetExistsError(proposal.error)) return <Redirect href={PROPOSAL_ROUTE} />;
  if (proposal.isError) {
    return <AnalysisError error={proposal.error} retrying={proposal.isFetching} onRetry={() => proposal.refetch()} />;
  }
  return <Analyzing />;
}

// Pencil 소비 분석 · 분석 중 (pWPd0): 아이콘 타일 자리에 모래시계 Lottie + 제목·설명 + 진행 막대. 버튼 없이 분석이 끝나면 다음 화면으로 넘어간다.
function Analyzing() {
  return (
    <View className="flex-1 items-center justify-center gap-5 bg-background px-10" accessibilityLiveRegion="polite">
      <LottieLoop source={ANALYZING_HOURGLASS} width={HOURGLASS_STYLE.width} height={HOURGLASS_STYLE.height} />
      <View className="items-center gap-2">
        <Text className="text-h2 text-foreground" accessibilityRole="header">
          지난 소비를 분석하고 있어요
        </Text>
        <Text className="text-center text-body-sm text-card-foreground">
          최근 카드·계좌 내역을 살펴보는 중이에요.{"\n"}잠시만 기다려 주세요.
        </Text>
      </View>
      <IndeterminateBar />
    </View>
  );
}

const TRACK_WIDTH = 160;
const SEGMENT_WIDTH = 64;
const SWEEP_MS = 1200;

// 진행률을 알 수 없는 요청이라 막대 조각이 트랙을 계속 가로지른다. 동작 줄이기 설정이면 멈춰 둔다.
function IndeterminateBar() {
  const reducedMotion = useReducedMotion();
  const offset = useSharedValue(-SEGMENT_WIDTH);

  React.useEffect(() => {
    if (reducedMotion) return;
    offset.value = withRepeat(withTiming(TRACK_WIDTH, { duration: SWEEP_MS, easing: Easing.inOut(Easing.ease) }), -1);
    return () => cancelAnimation(offset);
  }, [offset, reducedMotion]);

  const sweep = useAnimatedStyle(() => ({ transform: [{ translateX: reducedMotion ? 0 : offset.value }] }));

  return (
    <View className="h-1.5 w-40 overflow-hidden rounded-full bg-muted" accessibilityRole="progressbar" accessibilityLabel="분석 중">
      <Animated.View style={sweep}>
        <View className="h-1.5 w-16 rounded-full bg-primary" />
      </Animated.View>
    </View>
  );
}

type AnalysisErrorProps = {
  error: unknown;
  retrying: boolean;
  onRetry: () => void;
};

// Pencil spending-analysis/error (wcbvZ).
function AnalysisError({ error, retrying, onRetry }: AnalysisErrorProps) {
  const insets = useSafeAreaInsets();

  return (
    <View className="flex-1 bg-background">
      <View className="flex-1 items-center justify-center gap-5 px-10" accessibilityLiveRegion="polite">
        <View className="h-16 w-16 items-center justify-center rounded-full bg-destructive-muted">
          <Icon as={CircleAlert} size={28} className="text-destructive" />
        </View>
        <View className="items-center gap-2">
          <Text className="text-h2 text-foreground" accessibilityRole="header">
            소비를 분석하지 못했어요
          </Text>
          <Text className="text-center text-body-sm text-card-foreground">{proposalErrorMessage(error)}</Text>
        </View>
      </View>
      <View className="px-6 pt-3" style={{ paddingBottom: Math.max(insets.bottom, MIN_BOTTOM_INSET) }}>
        <Button size="lg" className="h-button-lg rounded-lg" onPress={onRetry} disabled={retrying}>
          <Text>{retrying ? "다시 분석하는 중…" : "다시 시도"}</Text>
        </Button>
      </View>
    </View>
  );
}

export { SpendingAnalyzingScreen };
