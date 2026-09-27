import { Redirect, useRouter } from "expo-router";
import { Receipt, WalletMinimal, WifiOff } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { CountUpAmount } from "@/components/ui/count-up-amount";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { needsConfirmation, useCurrentBudget } from "@/features/budget/api/queries";
import { envelopeIcon, envelopeTone } from "@/features/budget/catalog";
import { PROPOSAL_FROM_HOME_HREF } from "@/features/budget/components/BudgetProposalScreen";
import {
  budgetPeriodLabel,
  envelopeHealth,
  usedBarPercent,
  type BudgetEnvelope,
  type EnvelopeHealth,
} from "@/features/budget/model";
import { useTransactionList } from "@/features/transaction/api/queries";
import { TransactionRow } from "@/features/transaction/components/TransactionRow";
import { currentMonthKey } from "@/lib/date";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

const BUDGET_ROUTE = "/budget";

type EnvelopeDetailScreenProps = {
  /** 라우트 파라미터에서 검증한 봉투 id. 형식이 틀리면 null */
  envelopeId: number | null;
};

/**
 * PAGE-23 봉투 상세. 잔액은 GET /budgets/current 의 그 봉투 값이고 거래는 GET /transactions 의 envelopeId 필터다.
 * 거래 필터의 month 는 주기 시작월이라 주기가 두 달에 걸치면 목록이 주기와 딱 맞지 않는다 (TBD).
 * 확정 전(PROPOSED) 주기는 예산 탭과 같게 예산 확정 화면으로 보낸다(사용자 결정 2026-09-12).
 * Pencil 봉투 상세 · 금액 대안 (ola4D): 요약은 카드 없이 잔액이 화면에서 가장 크고 막대는 화면 폭 전체.
 */
function EnvelopeDetailScreen({ envelopeId }: EnvelopeDetailScreenProps) {
  const router = useRouter();
  const budget = useCurrentBudget();
  const envelope = envelopeId === null ? undefined : budget.data?.envelopes.find((item) => item.envelopeId === envelopeId);
  const month = budget.data?.month;
  const list = useTransactionList(
    { month: month ?? currentMonthKey(), envelopeId: envelopeId ?? 0 },
    month !== undefined && envelope !== undefined
  );
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];

  const goBack = () => {
    if (router.canGoBack()) router.back();
    else router.replace(BUDGET_ROUTE);
  };

  if (needsConfirmation(budget)) return <Redirect href={PROPOSAL_FROM_HOME_HREF} />;

  return (
    <Screen>
      <ScreenHeader title={envelope?.name ?? "봉투"} onBack={goBack} />

      {budget.isPending ? (
        <EnvelopeSkeleton />
      ) : budget.data === undefined ? (
        <EmptyState
          icon={WifiOff}
          title="예산을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => budget.refetch(), disabled: budget.isFetching }}
        />
      ) : envelope === undefined ? (
        <EmptyState
          icon={WalletMinimal}
          title="봉투를 찾을 수 없어요"
          description="예산에서 봉투를 다시 골라 주세요."
          action={{ label: "예산 보기", onPress: () => router.replace(BUDGET_ROUTE) }}
        />
      ) : (
        <ScreenFlatList
          data={items}
          keyExtractor={(transaction) => String(transaction.id)}
          contentContainerClassName="px-6 pb-8"
          ListHeaderComponent={
            <View className="gap-5 pb-2">
              <EnvelopeSummary envelope={envelope} period={budgetPeriodLabel(budget.data)} />
              <Text className="text-h3 text-foreground" accessibilityRole="header">
                거래 내역
              </Text>
            </View>
          }
          renderItem={({ item }) => <TransactionRow transaction={item} onPress={() => router.push(`/transaction/${item.id}`)} />}
          ListEmptyComponent={<TransactionsPlaceholder list={list} />}
          onEndReachedThreshold={0.4}
          onEndReached={() => {
            if (list.hasNextPage && !list.isFetchingNextPage) void list.fetchNextPage();
          }}
          refreshing={list.isRefetching && !list.isFetchingNextPage}
          onRefresh={() => {
            void budget.refetch();
            void list.refetch();
          }}
          ListFooterComponent={
            list.isFetchingNextPage ? (
              <Skeleton className="mt-3 h-14 w-full rounded-md" />
            ) : list.isFetchNextPageError ? (
              <Pressable accessibilityRole="button" className="items-center py-4" onPress={() => list.fetchNextPage()}>
                <Text className="text-label text-primary">더 불러오지 못했어요. 다시 시도</Text>
              </Pressable>
            ) : null
          }
        />
      )}
    </Screen>
  );
}

const BAR_CLASS: Record<EnvelopeHealth, string> = {
  good: "bg-positive",
  warning: "bg-warning",
  over: "bg-destructive",
  unset: "bg-muted",
};

type EnvelopeSummaryProps = {
  envelope: BudgetEnvelope;
  period: string;
};

// 기간 · 잔액 · 사용률 막대 · 예산/사용액. 예산 탭 남은 예산과 같은 흰 카드다(2026-09-17 사용자 결정). 금액은 서버 값만 쓴다(규칙 80).
function EnvelopeSummary({ envelope, period }: EnvelopeSummaryProps) {
  const health = envelopeHealth(envelope);
  const used = usedBarPercent(envelope.remainingRate);

  return (
    <View className="gap-3 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
      <View className="flex-row items-center gap-2.5">
        <View className={cn("h-7 w-7 items-center justify-center rounded-md", envelopeTone(envelope.envelopeId).tile)}>
          <Icon as={envelopeIcon(envelope.envelopeId)} size={16} className={envelopeTone(envelope.envelopeId).icon} />
        </View>
        <Text className="text-label tabular-nums text-card-foreground">{period}</Text>
      </View>
      {health === "unset" || envelope.remaining === null ? (
        <Text className="text-amount-lg tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
          예산 미설정
        </Text>
      ) : (
        <CountUpAmount
          value={envelope.remaining}
          format={(shown) => (health === "over" ? `${formatKRW(shown, { sign: "never" })} 초과` : `${formatKRW(shown)} 남음`)}
          className={cn("text-amount-lg tabular-nums", health === "over" ? "text-destructive" : "text-foreground")}
        />
      )}
      <View
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        accessible
        accessibilityRole="progressbar"
        accessibilityLabel={`${envelope.name} 사용률`}
        accessibilityValue={{ min: 0, max: 100, now: used }}
      >
        <View className={cn("h-full rounded-full", BAR_CLASS[health])} style={{ width: `${used}%` }} />
      </View>
      <View className="flex-row justify-between">
        <Text className="text-caption tabular-nums text-card-foreground">
          {envelope.confirmed === null ? "예산 미설정" : `예산 ${formatKRW(envelope.confirmed)}`}
        </Text>
        <Text className="text-caption tabular-nums text-card-foreground">
          {envelope.spent === null ? "" : `사용 ${formatKRW(envelope.spent)}`}
        </Text>
      </View>
    </View>
  );
}

type TransactionsPlaceholderProps = {
  list: ReturnType<typeof useTransactionList>;
};

// 목록 자리의 로딩·오류·빈 상태. 잔액 카드는 이미 떠 있으니 화면 전체를 막지 않는다.
function TransactionsPlaceholder({ list }: TransactionsPlaceholderProps) {
  if (list.isPending) return <ListSkeleton />;
  if (list.data === undefined) {
    return (
      <EmptyState
        icon={WifiOff}
        title="거래 내역을 불러오지 못했어요"
        description="연결 상태를 확인한 뒤 다시 시도해 주세요."
        action={{ label: "다시 시도", onPress: () => list.refetch(), disabled: list.isFetching }}
      />
    );
  }
  return <EmptyState icon={Receipt} title="이번 달 거래가 아직 없어요" description="이 봉투에서 쓴 결제가 생기면 여기에 쌓여요." />;
}

const SKELETON_ROWS = [1, 2, 3, 4];

function ListSkeleton() {
  return (
    <View className="gap-2 pt-1" accessible accessibilityLabel="불러오는 중">
      {SKELETON_ROWS.map((row) => (
        <Skeleton key={row} className="h-14 w-full rounded-md" />
      ))}
    </View>
  );
}

function EnvelopeSkeleton() {
  return (
    <View className="gap-4 px-6 pt-3" accessible accessibilityLabel="불러오는 중">
      <Skeleton className="h-5 w-28" />
      <Skeleton className="h-11 w-56" />
      <Skeleton className="h-2 w-full rounded-full" />
      <Skeleton className="h-6 w-24" />
      <ListSkeleton />
    </View>
  );
}

export { EnvelopeDetailScreen };
export type { EnvelopeDetailScreenProps };
