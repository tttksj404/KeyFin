import { useRouter } from "expo-router";
import { Coins, WifiOff } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { flattenCoinHistory, useCoinBalance, useCoinHistory } from "@/features/shop/api/queries";
import { coinReasonIcon } from "@/features/shop/catalog";
import {
  coinCountLabel,
  coinDeltaLabel,
  coinDeltaSpoken,
  groupCoinHistoryByDate,
  type CoinDateGroup,
  type CoinHistoryItem,
} from "@/features/shop/model";
import { currentDateKey, formatDateGroupLabel } from "@/lib/date";
import { cn } from "@/lib/utils";

const HOME_ROUTE = "/";

/**
 * PAGE-30 코인 이력 (FR-GAM-08, P1). 홈 헤더 코인 배지에서 들어온다.
 * 위에는 GET /fin-coins/balance 의 보유 코인, 아래에는 GET /fin-coins 이력을 지급 기준일로 묶어 최신순으로 보여 준다.
 * 사유 문구(reasonText)·증감·잔액은 서버 값 그대로다. 잔액 조회만 실패하면 목록은 두고 잔액 자리에서 다시 부른다 (규칙 50).
 * Pencil PAGE-30 코인 이력 (f7YQj) · 빈 상태 (e1UFei) · 불러오는 중 (PK3Xv) · 오류 (Gi7XY).
 */
function CoinHistoryScreen() {
  const router = useRouter();
  const balance = useCoinBalance();
  const history = useCoinHistory();
  const groups = groupCoinHistoryByDate(flattenCoinHistory(history.data));
  const todayKey = currentDateKey();

  const refreshAll = () => {
    void balance.refetch();
    void history.refetch();
  };

  return (
    <Screen>
      <ScreenHeader title="코인" onBack={() => (router.canGoBack() ? router.back() : router.replace(HOME_ROUTE))} />

      {history.isPending ? (
        <CoinHistorySkeleton />
      ) : history.data === undefined ? (
        // 첫 쪽부터 실패했을 때만 화면 전체를 오류로 둔다. 다음 쪽 실패는 목록을 두고 끝에서 다시 부른다.
        <View className="flex-1 justify-center pb-20">
          <EmptyState
            icon={WifiOff}
            title="코인 이력을 불러오지 못했어요"
            description="연결 상태를 확인한 뒤 다시 시도해 주세요."
            action={{ label: "다시 시도", onPress: refreshAll, disabled: history.isFetching }}
          />
        </View>
      ) : (
        <ScreenFlatList
          data={groups}
          keyExtractor={(group) => group.dateKey}
          contentContainerClassName="gap-8 px-6 pb-8"
          ListHeaderComponent={
            <BalanceCard
              balance={balance.data}
              pending={balance.isPending}
              failed={balance.isError}
              retrying={balance.isFetching}
              onRetry={() => balance.refetch()}
            />
          }
          renderItem={({ item }) => <DateGroup group={item} todayKey={todayKey} />}
          onEndReachedThreshold={0.4}
          onEndReached={() => {
            if (history.hasNextPage && !history.isFetchingNextPage) void history.fetchNextPage();
          }}
          refreshing={(history.isRefetching && !history.isFetchingNextPage) || balance.isRefetching}
          onRefresh={refreshAll}
          ListEmptyComponent={
            <View className="gap-1 rounded-lg bg-muted p-4">
              <Text className="text-label text-foreground">아직 코인 이력이 없어요</Text>
              <Text className="text-body-sm text-card-foreground">매일 처음 앱에 들어오면 출석 코인 10개를 받아요.</Text>
            </View>
          }
          ListFooterComponent={
            history.isFetchingNextPage ? (
              <Skeleton className="h-14 w-full rounded-md" />
            ) : history.isFetchNextPageError ? (
              <Pressable accessibilityRole="button" className="items-center py-4" onPress={() => history.fetchNextPage()}>
                <Text className="text-label text-primary">더 불러오지 못했어요. 다시 시도</Text>
              </Pressable>
            ) : null
          }
        />
      )}
    </Screen>
  );
}

type BalanceCardProps = {
  balance: number | undefined;
  pending: boolean;
  failed: boolean;
  retrying: boolean;
  onRetry: () => void;
};

// Pencil Summary: 흰 카드 + '보유 코인' + 노란 코인 원(홈 CoinBadge 와 같은 warning 색) + amount-lg 숫자.
function BalanceCard({ balance, pending, failed, retrying, onRetry }: BalanceCardProps) {
  const count = balance === undefined ? null : coinCountLabel(balance);

  return (
    <View
      className="gap-2 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none"
      accessible={count !== null}
      accessibilityLabel={count === null ? undefined : `보유 코인 ${count}개`}
    >
      <Text className="text-label text-card-foreground">보유 코인</Text>
      <View className="flex-row items-center gap-2">
        <View className="h-7 w-7 items-center justify-center rounded-full bg-warning" accessible={false}>
          <Icon as={Coins} size={16} className="text-foreground" />
        </View>
        {pending ? (
          <Skeleton className="h-11 w-32 rounded-md" />
        ) : count === null ? (
          <Text className="text-amount-lg tabular-nums text-foreground">—</Text>
        ) : (
          <Text className="text-amount-lg tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
            {count}
          </Text>
        )}
      </View>
      {failed && count === null ? (
        <View className="flex-row items-center justify-between gap-3" accessibilityLiveRegion="polite">
          <Text className="flex-1 text-body-sm text-card-foreground">잔액을 불러오지 못했어요.</Text>
          <Pressable accessibilityRole="button" accessibilityState={{ disabled: retrying }} disabled={retrying} hitSlop={10} onPress={onRetry}>
            <Text className={cn("text-label", retrying ? "text-card-foreground" : "text-primary")}>다시 시도</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

// 날짜 묶음 제목은 알림함·결제 캘린더와 같이 text-h3 검정. 행은 카드가 아니라 아래 선으로 나눈다 (Pencil Row stroke bottom).
function DateGroup({ group, todayKey }: { group: CoinDateGroup; todayKey: string }) {
  return (
    <View className="gap-1">
      <Text className="text-h3 text-foreground" accessibilityRole="header">
        {formatDateGroupLabel(group.dateKey, todayKey)}
      </Text>
      <View>
        {group.items.map((item) => (
          <CoinRow key={item.id} item={item} />
        ))}
      </View>
    </View>
  );
}

// 적립은 초록 +, 사용은 검정 - — 색만으로 전하지 않고 부호와 읽기 문구를 함께 둔다 (규칙 40).
function CoinRow({ item }: { item: CoinHistoryItem }) {
  const balanceAfter = coinCountLabel(item.balanceAfter);

  return (
    <View
      className="flex-row items-center gap-3 border-b border-border py-3.5"
      accessible
      accessibilityLabel={`${item.reasonText}, ${coinDeltaSpoken(item.delta)}, 잔액 ${balanceAfter}코인`}
    >
      <View className="h-10 w-10 items-center justify-center rounded-full bg-accent">
        <Icon as={coinReasonIcon(item.reason)} size={20} className="text-primary" />
      </View>
      <View className="flex-1 gap-0.5">
        <Text className="text-body text-foreground" numberOfLines={1}>
          {item.reasonText}
        </Text>
        <Text className="text-caption tabular-nums text-card-foreground">잔액 {balanceAfter}</Text>
      </View>
      <Text
        className={cn("text-amount-sm tabular-nums", item.delta > 0 ? "text-positive" : "text-foreground")}
        maxFontSizeMultiplier={1.3}
      >
        {coinDeltaLabel(item.delta)}
      </Text>
    </View>
  );
}

const SKELETON_GROUPS = [
  { id: "today", rows: [1, 2] },
  { id: "yesterday", rows: [1, 2] },
];

// Pencil 불러오는 중 (PK3Xv): 잔액 카드 자리 + 날짜 제목·행 자리.
function CoinHistorySkeleton() {
  return (
    <View className="gap-8 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      <Skeleton className="h-28 w-full rounded-2xl" />
      {SKELETON_GROUPS.map((group) => (
        <View key={group.id} className="gap-3">
          <Skeleton className="h-6 w-16 rounded-sm" />
          {group.rows.map((row) => (
            <Skeleton key={row} className="h-14 w-full rounded-md" />
          ))}
        </View>
      ))}
    </View>
  );
}

export { CoinHistoryScreen };
