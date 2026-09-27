import { useLocalSearchParams, useRouter } from "expo-router";
import { ChevronLeft, ChevronRight, Receipt, WifiOff } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useAccounts } from "@/features/account/api/queries";
import { linkedCards } from "@/features/account/model";
import { ENVELOPE_CATALOG } from "@/features/budget/catalog";
import { useLinkCandidates } from "@/features/link/api/queries";
import { transactionKeys, useTransactionList } from "@/features/transaction/api/queries";
import { FilterSelect, type SelectOption } from "@/features/transaction/components/FilterSelect";
import { TransactionRow } from "@/features/transaction/components/TransactionRow";
import { monthFilterLabel, parseTransactionFilter, type TransactionFilter } from "@/features/transaction/model";
import { useRefetchStaleOnFocus } from "@/hooks/use-refetch-stale-on-focus";
import { currentMonthKey, shiftMonthKey } from "@/lib/date";

const ASSETS_ROUTE = "/assets";

/** 필터를 바꿀 때 넘기는 검색 파라미터. undefined 는 그 필터를 푼다 */
type FilterParams = { month?: string; envelopeId?: string; accountId?: string; cardId?: string };

// 거래 내역 전체보기 (자산 탭 "전체보기", FR-TXN-09). Pencil 시안 없음 — 자산 탭 행 모양을 따른다.
// 필터는 검색 파라미터로 둔다(규칙 10: 딥링크로 복원되는 필터). 행을 탭하면 거래 상세(PAGE-21)로 간다.
function TransactionListScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const thisMonth = currentMonthKey();
  const filter = parseTransactionFilter(params, thisMonth);
  const list = useTransactionList(filter);
  useRefetchStaleOnFocus(transactionKeys.all);
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];

  const setFilter = (next: FilterParams) => router.setParams(next);

  return (
    <Screen>
      <ScreenHeader
        title="거래 내역"
        onBack={() => (router.canGoBack() ? router.back() : router.replace(ASSETS_ROUTE))}
      />

      <MonthStepper
        month={filter.month}
        canGoNext={filter.month < thisMonth}
        onChange={(month) => setFilter({ month })}
      />
      <FilterSelects filter={filter} onChange={setFilter} />

      {list.isPending ? (
        <ListSkeleton />
      ) : list.data === undefined ? (
        // 첫 쪽부터 실패했을 때만 화면 전체를 오류로 둔다. 다음 쪽 실패는 목록을 유지하고 끝에서 다시 부른다.
        <EmptyState
          icon={WifiOff}
          title="거래 내역을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => list.refetch(), disabled: list.isFetching }}
        />
      ) : (
        <ScreenFlatList
          overlapHeader={false}
          data={items}
          keyExtractor={(transaction) => String(transaction.id)}
          renderItem={({ item }) => (
            <TransactionRow transaction={item} onPress={() => router.push(`/transaction/${item.id}`)} />
          )}
          contentContainerClassName="px-6 pb-8"
          onEndReachedThreshold={0.4}
          onEndReached={() => {
            if (list.hasNextPage && !list.isFetchingNextPage) void list.fetchNextPage();
          }}
          refreshing={list.isRefetching && !list.isFetchingNextPage}
          onRefresh={() => list.refetch()}
          ListEmptyComponent={
            <EmptyState icon={Receipt} title="거래 내역이 없어요" description="다른 달이나 필터를 골라 보세요." />
          }
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

type MonthStepperProps = {
  month: string;
  canGoNext: boolean;
  onChange: (month: string) => void;
};

// 이번 달 이후는 거래가 없으니 다음 달로 넘기지 않는다.
function MonthStepper({ month, canGoNext, onChange }: MonthStepperProps) {
  return (
    <View className="flex-row items-center justify-center gap-4 pb-3">
      <Pressable accessibilityRole="button" accessibilityLabel="이전 달" hitSlop={12} onPress={() => onChange(shiftMonthKey(month, -1))}>
        <Icon as={ChevronLeft} size={20} className="text-foreground" />
      </Pressable>
      <Text className="text-h3 tabular-nums text-foreground" accessibilityLiveRegion="polite">
        {monthFilterLabel(month)}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="다음 달"
        accessibilityState={{ disabled: !canGoNext }}
        disabled={!canGoNext}
        hitSlop={12}
        onPress={() => onChange(shiftMonthKey(month, 1))}
      >
        <Icon as={ChevronRight} size={20} className={canGoNext ? "text-foreground" : "text-card-foreground/40"} />
      </Pressable>
    </View>
  );
}

type FilterSelectsProps = {
  filter: TransactionFilter;
  onChange: (next: FilterParams) => void;
};

const ALL_KEY = "all";

const ENVELOPE_OPTIONS: SelectOption[] = [
  { key: ALL_KEY, label: "전체 봉투" },
  ...ENVELOPE_CATALOG.map((envelope) => ({ key: String(envelope.id), label: envelope.name })),
];

/** 계좌·카드 선택값. 한 목록에서 고르므로 종류를 앞에 붙인다(id 는 계좌·카드끼리 겹친다) */
function assetKeyOf(filter: TransactionFilter): string {
  if (filter.accountId !== undefined) return `account:${filter.accountId}`;
  if (filter.cardId !== undefined) return `card:${filter.cardId}`;
  return ALL_KEY;
}

function assetParamsOf(key: string): FilterParams {
  const [kind, id] = key.split(":");
  if (kind === "account") return { accountId: id, cardId: undefined };
  if (kind === "card") return { cardId: id, accountId: undefined };
  return { accountId: undefined, cardId: undefined };
}

// 봉투 선택 + 계좌·카드 선택을 나란히 둔다. 계좌는 GET /accounts, 카드는 카드 API 가 없어 금융망 후보에서 온다 —
// 둘 다 못 불러왔거나 연결된 게 없으면 그쪽 선택만 비활성이다.
function FilterSelects({ filter, onChange }: FilterSelectsProps) {
  const accounts = useAccounts();
  const candidates = useLinkCandidates();
  const assetOptions: SelectOption[] = [
    { key: ALL_KEY, label: "전체 계좌·카드" },
    ...(accounts.data ?? []).map((account) => ({
      key: `account:${account.accountId}`,
      label: `${account.bankName} ${account.maskedNo.slice(-4)}`,
      section: "계좌",
    })),
    ...(candidates.data ? linkedCards(candidates.data) : []).map((card) => ({
      key: `card:${card.cardId}`,
      label: card.cardName,
      section: "카드",
    })),
  ];

  return (
    <View className="flex-row gap-2 px-6 pb-3">
      <FilterSelect
        title="봉투"
        options={ENVELOPE_OPTIONS}
        selectedKey={filter.envelopeId === undefined ? ALL_KEY : String(filter.envelopeId)}
        onSelect={(key) => onChange({ envelopeId: key === ALL_KEY ? undefined : key })}
      />
      <FilterSelect
        title="계좌·카드"
        options={assetOptions}
        selectedKey={assetKeyOf(filter)}
        disabled={assetOptions.length === 1}
        onSelect={(key) => onChange(assetParamsOf(key))}
      />
    </View>
  );
}

const SKELETON_ROWS = [1, 2, 3, 4, 5];

function ListSkeleton() {
  return (
    <View className="gap-2 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      {SKELETON_ROWS.map((row) => (
        <Skeleton key={row} className="h-14 w-full rounded-md" />
      ))}
    </View>
  );
}

export { TransactionListScreen };
