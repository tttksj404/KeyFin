import type { UseMutationResult } from "@tanstack/react-query";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { WifiOff } from "lucide-react-native";
import * as React from "react";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/components/ui/button";
import { CountUpAmount } from "@/components/ui/count-up-amount";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import {
  useCachedBudgetProposal,
  useConfirmBudget,
  useCurrentBudget,
  type ConfirmBudgetVariables,
} from "@/features/budget/api/queries";
import { useAuthStore } from "@/features/auth/store";
import { envelopeIcon, envelopeTone } from "@/features/budget/catalog";
import { confirmErrorMessage, isAlreadyConfirmedError } from "@/features/budget/errors";
import {
  budgetPeriodLabel,
  proposalBasisKind,
  sumAmounts,
  toProposalRows,
  type Budget,
  type BudgetProposal,
  type ProposalBasisKind,
  type ProposalRow,
} from "@/features/budget/model";
import { saveOnboardingDone } from "@/lib/session-storage";
import { currentMonthKey } from "@/lib/date";
import { formatKRW, fromWon, toWon, type KRW } from "@/lib/money";
import { cn } from "@/lib/utils";

/** 슬라이더 범위. 명세에 상한이 없어 시안 기준 15만원·1천원 단위로 두고, 제안액이 더 크면 그만큼 늘린다. (TBD) */
const SLIDER_BASE_MAX = 150000;
/** 승인 금액은 1,000원 단위다(BUDGET_005, 노션 예산 승인·조정) */
const SLIDER_STEP = 1000;

const CTA_LABEL = "이 예산으로 시작하기";

/** 온보딩에서는 승인 뒤 입주 연출(PAGE-08)을 거쳐 홈으로 간다 (유저 플로우 v2 온보딩 레인) */
const MOVING_IN_ROUTE = "/character/moving-in";
const HOME_ROUTE = "/";

/**
 * 홈·예산 탭이 확정 전(PROPOSED) 예산을 보고 이 화면으로 강제로 보낼 때 쓰는 주소 (사용자 결정 2026-09-12, 노션 "PROPOSED → 확정 화면 강제 이동").
 * 이렇게 들어오면 뒤로가기를 숨기고, 확정하면 입주 연출 대신 홈으로 돌아간다.
 */
export const PROPOSAL_FROM_HOME_HREF = { pathname: "/onboarding/budget-proposal", params: { next: "home" } } as const;

/** 하단 CTA 가 안전 영역이 없는 기기에서도 탭바처럼 띄워지는 최소 여백 (components/ui/tab-bar.tsx 와 같은 기준) */
const MIN_BOTTOM_INSET = 12;

type ConfirmMutation = UseMutationResult<void, Error, ConfirmBudgetVariables>;

// Pencil budget-proposal (g1fhiV) · budget-proposal/full (VAJgp). 온보딩 화면이라 탭바가 없고 CTA 가 하단에 고정된다.
// 금액·budgetId 는 GET /budgets/current(PROPOSED)에서 온다. 제안 API(POST)는 주기당 한 번이라 여기서 부르지 않고,
// 온보딩 분석 결과(월평균·근거)가 캐시에 있을 때만 근거를 함께 보여 준다.
function BudgetProposalScreen() {
  const params = useLocalSearchParams();
  const fromHome = params.next === "home";
  const nextRoute = fromHome ? HOME_ROUTE : MOVING_IN_ROUTE;
  const current = useCurrentBudget();
  const analysis = useCachedBudgetProposal(currentMonthKey());
  const confirm = useConfirmBudget();

  // 들어왔는데 이미 확정된 주기면 고칠 수 없으니 다음 단계로 넘긴다. 방금 확정한 경우는 확정 콜백이 넘긴다.
  if (current.data?.status === "CONFIRMED" && confirm.isIdle) return <Redirect href={nextRoute} />;

  return (
    <Screen>
      <ProposalHeader showBack={!fromHome} />
      {current.isPending ? (
        <ProposalSkeleton />
      ) : current.isError ? (
        <EmptyState
          icon={WifiOff}
          title="예산 제안을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => current.refetch(), disabled: current.isFetching }}
        />
      ) : (
        <ProposalForm budget={current.data} analysis={analysis.data} confirm={confirm} nextRoute={nextRoute} />
      )}
    </Screen>
  );
}

// Pencil Header (wwtVz): bg-card · 뒤로가기 + 제목. 안전 영역 상단은 라우트의 SafeAreaView 가 맡는다.
// 홈에서 강제로 왔으면 확정 전에는 돌아갈 곳이 없어 뒤로가기를 숨긴다.
function ProposalHeader({ showBack }: { showBack: boolean }) {
  const router = useRouter();

  return (
    <ScreenHeader
    flat
      title="이번 달 예산 설정"
      className="bg-card"
      onBack={showBack ? () => (router.canGoBack() ? router.back() : router.replace("/budget")) : undefined}
    />
  );
}

const BASIS_DESCRIPTION: Record<ProposalBasisKind, string> = {
  history: "지난 소비를 분석해 봉투별 금액을 제안했어요. 필요하면 바꿀 수 있어요.",
  template: "아직 분석할 소비가 없어 기본 예산으로 준비했어요. 필요하면 바꿀 수 있어요.",
  unknown: "봉투별로 제안된 금액이에요. 필요하면 바꿀 수 있어요.",
};

/** 총 예산 카드 아래 한 줄. 분석한 제안이면 근거와 월평균 합계, 기본 예산이면 근거만, 분석 결과가 없으면 봉투 수만 */
function proposalSummary(kind: ProposalBasisKind, rows: ProposalRow[], analysis: BudgetProposal | undefined): string {
  const count = `봉투 ${rows.length}개`;
  if (kind === "history" && analysis) return `${count} · ${analysis.basis} ${formatKRW(sumAmounts(rows.map((row) => row.monthlyAvg ?? "0")))}`;
  if (kind === "template" && analysis) return `${count} · ${analysis.basis}`;
  return count;
}

type ProposalFormProps = {
  budget: Budget;
  analysis: BudgetProposal | undefined;
  confirm: ConfirmMutation;
  nextRoute: string;
};

function ProposalForm({ budget, analysis, confirm, nextRoute }: ProposalFormProps) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [dialogOpen, setDialogOpen] = React.useState(false);

  const kind = proposalBasisKind(budget, analysis);
  const rows = React.useMemo(() => toProposalRows(budget, analysis), [budget, analysis]);
  const period = budgetPeriodLabel(budget);

  // 제안액이 기본값이고, 사용자가 만진 봉투만 덮어쓴다.
  const [edited, setEdited] = React.useState<Record<number, KRW>>({});
  const amountOf = (row: ProposalRow): KRW => edited[row.envelopeId] ?? row.proposed;

  const total = sumAmounts(rows.map(amountOf));
  const summary = proposalSummary(kind, rows, analysis);

  const userId = useAuthStore((state) => state.user?.id ?? null);
  const completeOnboarding = useAuthStore((state) => state.completeOnboarding);
  // 첫 예산 확정 = 온보딩 완료(백엔드 합의 2026-09-11). 서버 필드가 생기기 전까지 기기에 기록해 홈 게이트가 이 값을 본다.
  const goNext = () => {
    completeOnboarding();
    if (userId !== null) void saveOnboardingDone(userId);
    router.replace(nextRoute);
  };

  // 확정은 주기당 1회라 확인을 받은 뒤 보낸다(노션 권고). 이미 확정됨(BUDGET_003)은 끝난 것으로 보고 넘긴다.
  const handleConfirm = () => {
    setDialogOpen(false);
    const entries = rows.map((row) => ({ envelopeId: row.envelopeId, amount: amountOf(row) }));
    confirm.mutate(
      { budgetId: budget.budgetId, entries },
      {
        onSuccess: goNext,
        onError: (error) => {
          if (isAlreadyConfirmedError(error)) goNext();
        },
      }
    );
  };

  return (
    <View className="flex-1">
      <ScreenScrollView className="flex-1" contentContainerClassName="gap-5 px-6 pb-6">
        <Text className="text-body-sm text-card-foreground">{BASIS_DESCRIPTION[kind]}</Text>

        {/* Pencil PAGE-07 예산 제안 (g1fhiV) 의 TotalCard: 흰 카드 안에 총 예산 · 근거 한 줄 (2026-09-17) */}
        <View className="gap-1 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
          <Text className="text-label text-card-foreground">{period} 총 예산</Text>
          <CountUpAmount value={total} className="text-amount-md tabular-nums text-foreground" />
          <Text className="text-caption tabular-nums text-card-foreground">{summary}</Text>
        </View>

        <View className="flex-row items-center justify-between">
          <Text className="text-h3 text-foreground" accessibilityRole="header">
            봉투별 금액
          </Text>
          <Text className="text-caption tabular-nums text-card-foreground">{rows.length}개</Text>
        </View>

        <View className="gap-3.5">
          {rows.map((row) => (
            <EnvelopeAmountRow
              key={row.envelopeId}
              row={row}
              amount={amountOf(row)}
              showMonthlyAvg={kind === "history"}
              onChange={(next) => setEdited((prev) => ({ ...prev, [row.envelopeId]: next }))}
            />
          ))}
        </View>
      </ScreenScrollView>

      <View className="gap-2 px-6 pt-3" style={{ paddingBottom: Math.max(insets.bottom, MIN_BOTTOM_INSET) }}>
        {confirm.isError ? (
          <Text className="text-caption text-destructive" accessibilityLiveRegion="polite">
            {confirmErrorMessage(confirm.error)}
          </Text>
        ) : null}
        <Button
          size="lg"
          className="h-button-lg rounded-lg"
          onPress={() => setDialogOpen(true)}
          disabled={confirm.isPending}
          accessibilityLabel={CTA_LABEL}
        >
          <Text>{confirm.isPending ? "저장하는 중…" : CTA_LABEL}</Text>
        </Button>
      </View>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-h3 text-foreground">이 예산으로 시작할까요?</DialogTitle>
            <DialogDescription className="text-body-sm text-card-foreground">
              시작하면 이번 예산({period})은 바꿀 수 없어요.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onPress={() => setDialogOpen(false)}>
              <Text>다시 볼게요</Text>
            </Button>
            <Button onPress={handleConfirm}>
              <Text>시작하기</Text>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </View>
  );
}

type EnvelopeAmountRowProps = {
  row: ProposalRow;
  amount: KRW;
  showMonthlyAvg: boolean;
  onChange: (amount: KRW) => void;
};

// Pencil 행(N9eU0 의 외식 행): 봉투 색 타일 + 이름 / 우측 금액칸 · 봉투 색 슬라이더 · 월평균 근거.
function EnvelopeAmountRow({ row, amount, showMonthlyAvg, onChange }: EnvelopeAmountRowProps) {
  const current = Number(toWon(amount));
  const max = Math.max(SLIDER_BASE_MAX, Math.ceil(Number(toWon(row.proposed)) / SLIDER_STEP) * SLIDER_STEP);

  return (
    <View className="gap-2">
      <View className="flex-row items-center justify-between">
        <View className="flex-row items-center gap-2.5">
          <View className={cn("h-7 w-7 items-center justify-center rounded-md", envelopeTone(row.envelopeId).tile)}>
            <Icon as={envelopeIcon(row.envelopeId)} size={16} className={envelopeTone(row.envelopeId).icon} />
          </View>
          <Text className="text-label text-foreground">{row.name}</Text>
        </View>
        <View className="rounded-md bg-muted px-3 py-1.5">
          <Text className="text-amount-sm tabular-nums text-foreground">{formatKRW(amount, { unit: false })}</Text>
        </View>
      </View>
      <Slider
        value={current}
        max={max}
        step={SLIDER_STEP}
        onValueChange={(next) => onChange(fromWon(BigInt(next)))}
        accessibilityLabel={`${row.name} 금액`}
        fillClassName={envelopeTone(row.envelopeId).bar}
      />
      {showMonthlyAvg && row.monthlyAvg !== null ? (
        <Text className="text-caption tabular-nums text-card-foreground">월평균 {formatKRW(row.monthlyAvg)}</Text>
      ) : null}
    </View>
  );
}

const SKELETON_ROWS = [1, 2, 3, 4, 5, 6, 7];

function ProposalSkeleton() {
  return (
    <View className="gap-5 px-6 pt-5" accessible accessibilityLabel="불러오는 중">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-28 w-full rounded-2xl" />
      <View className="gap-3.5">
        {SKELETON_ROWS.map((row) => (
          <View key={row} className="gap-2">
            <Skeleton className="h-7 w-full" />
            <Skeleton className="h-5 w-full rounded-full" />
          </View>
        ))}
      </View>
    </View>
  );
}

export { BudgetProposalScreen, CTA_LABEL };
