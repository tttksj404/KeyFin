import { useRouter } from "expo-router";
import { CheckCheck, CircleAlert, WifiOff } from "lucide-react-native";
import { useEffect, useState } from "react";
import { View } from "react-native";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import {
  flattenPending,
  useBulkClassifyTransactions,
  useClassifyTransaction,
  usePendingTransactions,
  useSubcategories,
} from "@/features/transaction/api/queries";
import { SubcategorySheet } from "@/features/transaction/components/SubcategorySheet";
import { bulkClassifyErrorMessage, classifyErrorMessage } from "@/features/transaction/errors";
import {
  merchantLabel,
  resolvePendingFocus,
  suggestedForBulk,
  toSuggestedBulkRequest,
  transactionDateTimeLabel,
  type ClassifyRequest,
  type Transaction,
} from "@/features/transaction/model";
import { formatKRW, subtractKRW } from "@/lib/money";

const HOME_ROUTE = "/";
const OTHER_CATEGORY_LABEL = "다른 카테고리";

/**
 * PAGE-22 미확정 정리. 확인이 필요한 결제(GET /transactions/pending)를 한 화면에 모아
 * 건별로 제안 세분류를 확정하거나 세분류 시트(PAGE-20)로 바꾼다 (FR-TXN-03). Pencil 시안 없음.
 * 아래 버튼은 제안 세분류가 있는 건을 한 번에 확정한다(PUT /transactions/classifications, P1) — 제안이 없는 건은 빠지고,
 * 서버가 한 건이라도 실패하면 전체를 되돌리므로 확인 창에서 그 사실을 먼저 알린다. 저녁 세션 코인은 아직이다.
 * 확정한 거래는 미확정 캐시에서 빠지므로 목록이 줄고, 다 비우면 빈 상태가 된다.
 *
 * 알림("새로 정리할 거래가 있어요")에서 오면 그 거래 id 가 focusId 로 온다(2026-09-21 사용자 요청). 목록에서 그 거래를 찾아
 * 분류 창을 바로 열어 주고, 받은 쪽에 없으면 다음 쪽을 이어 받는다. 끝까지 없으면 이미 정리한 거래라 그렇다고만 알린다.
 */
type PendingCleanupScreenProps = {
  /** 분류 창을 바로 열어 줄 거래. 알림에서 넘어왔을 때만 온다 */
  focusId?: number | null;
};

function PendingCleanupScreen({ focusId = null }: PendingCleanupScreenProps) {
  const router = useRouter();
  const pending = usePendingTransactions();
  const classify = useClassifyTransaction();
  const bulk = useBulkClassifyTransactions();
  const [pickedTransaction, setPickedTransaction] = useState<Transaction | null>(null);
  // 알림에서 온 거래는 한 번만 열어 준다. 닫거나 확정한 뒤에도 계속 다시 열리면 화면을 쓸 수 없다.
  const [focusDone, setFocusDone] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const items = flattenPending(pending.data);
  const focus = focusId === null || focusDone || pending.data === undefined ? null : resolvePendingFocus(items, focusId, pending.hasNextPage);
  // 직접 고른 거래가 먼저다. 없으면 알림에서 온 거래를 연다 — 상태로 옮겨 담지 않고 그때그때 구한다.
  const sheetTransaction = pickedTransaction ?? (focus?.state === "found" ? focus.transaction : null);
  const subcategories = useSubcategories(sheetTransaction !== null);

  // 받은 쪽에 그 거래가 없으면 다음 쪽을 이어 받는다(서버가 20건씩 준다). 더 받기에 실패하면 멈춰 되풀이하지 않는다.
  const { hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage } = pending;
  const searching = focus?.state === "searching";
  useEffect(() => {
    if (searching && hasNextPage && !isFetchingNextPage && !isFetchNextPageError) void fetchNextPage();
  }, [searching, hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage]);

  const closeSheet = () => {
    setPickedTransaction(null);
    setFocusDone(true);
  };
  // 서버가 20건씩 주므로 더 남아 있으면 건수 뒤에 + 를 붙인다 — 받은 만큼만 세고 모르는 건 모른다고 적는다
  const countLabel = `${items.length}건${pending.hasNextPage ? "+" : ""}`;
  const submittingId = classify.isPending ? classify.variables?.transactionId : undefined;

  // 받아 둔 쪽 안에서 제안이 있는 건만 한 번에 보낸다. 다음 쪽은 확정 뒤 목록을 다시 받으면서 올라온다.
  const suggested = suggestedForBulk(items);
  const busy = classify.isPending || bulk.isPending;

  const runBulk = () => {
    if (bulk.isPending) return;
    bulk.mutate(toSuggestedBulkRequest(items), { onSuccess: () => setBulkOpen(false) });
  };

  const submit = (transaction: Transaction, request: ClassifyRequest) => {
    classify.mutate(
      { transactionId: transaction.id, request, txDate: transaction.txDate },
      { onSuccess: closeSheet }
    );
  };

  return (
    <Screen>
      <ScreenHeader
        title="미확정 정리"
        onBack={() => (router.canGoBack() ? router.back() : router.replace(HOME_ROUTE))}
      />

      {pending.isPending ? (
        <CleanupSkeleton />
      ) : pending.data === undefined ? (
        <EmptyState
          icon={WifiOff}
          title="미확정 결제를 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => pending.refetch(), disabled: pending.isFetching }}
        />
      ) : (
        <ScreenFlatList
          data={items}
          keyExtractor={(transaction) => String(transaction.id)}
          contentContainerClassName="gap-3 px-6 pb-8"
          refreshing={pending.isRefetching && !pending.isFetchingNextPage}
          onRefresh={() => pending.refetch()}
          onEndReachedThreshold={0.4}
          onEndReached={() => {
            if (pending.hasNextPage && !pending.isFetchingNextPage) void pending.fetchNextPage();
          }}
          ListHeaderComponent={
            <View className="gap-2">
              {focus?.state === "gone" ? (
                <View className="flex-row items-center gap-1.5 rounded-lg bg-info-muted p-3.5" accessibilityLiveRegion="polite">
                  <Icon as={CheckCheck} size={16} className="text-info" />
                  <Text className="shrink text-caption text-foreground">알림의 결제는 이미 정리했어요.</Text>
                </View>
              ) : null}
              {items.length === 0 ? null : (
                <Text className="pb-1 text-body-sm text-card-foreground" accessibilityLiveRegion="polite">
                  확인이 필요한 결제 {countLabel}
                </Text>
              )}
            </View>
          }
          ListFooterComponent={
            pending.isFetchingNextPage ? (
              <Skeleton className="h-32 w-full rounded-2xl" />
            ) : pending.isFetchNextPageError ? (
              <Button variant="outline" className="h-button-md rounded-lg" onPress={() => pending.fetchNextPage()}>
                <Text>더 불러오지 못했어요. 다시 시도</Text>
              </Button>
            ) : null
          }
          ListEmptyComponent={
            <EmptyState icon={CheckCheck} title="정리할 결제가 없어요" description="새 결제가 들어오면 여기에 모아 둘게요." />
          }
          renderItem={({ item }) => (
            <PendingCard
              transaction={item}
              isPending={submittingId === item.id || bulk.isPending}
              errorMessage={classify.isError && classify.variables?.transactionId === item.id ? classifyErrorMessage(classify.error) : null}
              onConfirm={() => item.subcategoryId !== null && submit(item, { subcategoryId: item.subcategoryId })}
              onOther={() => setPickedTransaction(item)}
            />
          )}
        />
      )}

      {bulk.isSuccess || suggested.length > 0 ? (
        <View className="gap-2 px-6 pb-8 pt-2">
          {bulk.isSuccess ? (
            <Text className="text-caption text-card-foreground" accessibilityLiveRegion="polite">
              {bulk.data.confirmed}건을 확정했어요.
              {bulk.data.pendingRemain > 0 ? ` 아직 ${bulk.data.pendingRemain}건 남았어요.` : ""}
            </Text>
          ) : null}
          {suggested.length === 0 ? null : (
            <Button
              size="lg"
              className="h-button-lg rounded-lg"
              disabled={busy}
              accessibilityState={{ disabled: busy }}
              accessibilityLabel={`제안대로 ${suggested.length}건 확정`}
              onPress={() => setBulkOpen(true)}
            >
              <Text>{bulk.isPending ? "확정하는 중" : `제안대로 ${suggested.length}건 확정`}</Text>
            </Button>
          )}
        </View>
      ) : null}

      <BulkConfirmDialog
        open={bulkOpen}
        count={suggested.length}
        pending={bulk.isPending}
        errorMessage={bulk.isError ? bulkClassifyErrorMessage(bulk.error) : null}
        onCancel={() => !bulk.isPending && setBulkOpen(false)}
        onConfirm={runBulk}
      />

      <SubcategorySheet
        visible={sheetTransaction !== null}
        subcategories={subcategories.data}
        selectedSubcategoryId={sheetTransaction?.subcategoryId ?? null}
        amount={sheetTransaction?.amount ?? "0"}
        disabled={classify.isPending}
        onSelect={(request) => sheetTransaction && submit(sheetTransaction, request)}
        onClose={closeSheet}
      />
    </Screen>
  );
}

type BulkConfirmDialogProps = {
  open: boolean;
  count: number;
  pending: boolean;
  errorMessage: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

// 여러 건이 한꺼번에 바뀌므로 무엇이 일어나는지 먼저 알린다 — 전부 되돌아간다는 점과 나중에 고칠 수 있다는 점.
function BulkConfirmDialog({ open, count, pending, errorMessage, onCancel, onConfirm }: BulkConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-h3 text-foreground">{count}건을 제안대로 확정할까요?</DialogTitle>
          <DialogDescription className="text-body-sm text-card-foreground">
            제안 세분류가 있는 결제만 한 번에 확정해요. 한 건이라도 안 되면 아무것도 바뀌지 않아요. 확정한 뒤에도 거래 상세에서 바꿀 수 있어요.
          </DialogDescription>
        </DialogHeader>
        {errorMessage === null ? null : (
          <View className="rounded-lg bg-destructive-muted p-3.5" accessibilityLiveRegion="polite">
            <Text className="text-caption text-foreground">{errorMessage}</Text>
          </View>
        )}
        <DialogFooter>
          <Button variant="secondary" disabled={pending} onPress={onCancel}>
            <Text>취소</Text>
          </Button>
          <Button disabled={pending} onPress={onConfirm}>
            <Text>{pending ? "확정하는 중" : "확정"}</Text>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type PendingCardProps = {
  transaction: Transaction;
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: () => void;
  onOther: () => void;
};

// 코치 말풍선(FR-TXN-03)과 같은 두 선택지를 카드로 편 것 — 제안 세분류 확정 또는 세분류 시트.
// 서버가 제안 세분류를 주지 않는 거래(subcategoryName null)는 세분류 시트 버튼만 둔다.
function PendingCard({ transaction, isPending, errorMessage, onConfirm, onOther }: PendingCardProps) {
  const confirmLabel = transaction.subcategoryName === null ? null : `${transaction.subcategoryName} 확정`;

  return (
    <View className="gap-3 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
      <View className="flex-row items-start justify-between gap-3">
        <View className="flex-1 gap-1">
          <Text className="text-h3 text-foreground" numberOfLines={1}>
            {merchantLabel(transaction)}
          </Text>
          <Text className="text-caption text-card-foreground">{transactionDateTimeLabel(transaction)}</Text>
        </View>
        <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
          {formatKRW(subtractKRW("0", transaction.amount))}
        </Text>
      </View>

      <View className="flex-row gap-2">
        {confirmLabel === null ? null : (
          <Button className="h-button-md flex-1 rounded-lg" disabled={isPending} accessibilityLabel={confirmLabel} onPress={onConfirm}>
            <Text numberOfLines={1}>{confirmLabel}</Text>
          </Button>
        )}
        <Button
          variant="outline"
          className="h-button-md flex-1 rounded-lg"
          disabled={isPending}
          accessibilityLabel={OTHER_CATEGORY_LABEL}
          onPress={onOther}
        >
          <Text numberOfLines={1}>{OTHER_CATEGORY_LABEL}</Text>
        </Button>
      </View>

      {errorMessage === null ? null : (
        <View className="flex-row items-center gap-1.5" accessibilityLiveRegion="polite">
          <Icon as={CircleAlert} size={16} className="text-destructive" />
          <Text className="shrink text-caption text-destructive">{errorMessage}</Text>
        </View>
      )}
    </View>
  );
}

const SKELETON_CARDS = [1, 2, 3];

function CleanupSkeleton() {
  return (
    <View className="gap-3 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      {SKELETON_CARDS.map((card) => (
        <Skeleton key={card} className="h-32 w-full rounded-2xl" />
      ))}
    </View>
  );
}

export { PendingCleanupScreen };
