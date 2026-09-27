import { useRouter } from "expo-router";
import { ChevronRight, CreditCard, Receipt, WalletMinimal } from "lucide-react-native";
import * as React from "react";
import { Pressable, View } from "react-native";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Screen, ScreenScrollView, useHeaderlessTop } from "@/components/ui/screen";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useAccounts } from "@/features/account/api/queries";
import { balanceAsOfLabel, linkedCards, totalBalance, type LinkedAccount, type LinkedCard } from "@/features/account/model";
import { useLinkCandidates } from "@/features/link/api/queries";
import { BankLogoTile } from "@/features/link/components/BankLogoTile";
import { CandidatesErrorState } from "@/features/link/components/CandidatesErrorState";
import { useCardBillings, usePaymentCalendar } from "@/features/payment/api/queries";
import { calendarEntryIcon } from "@/features/payment/catalog";
import { findCardBilling, upcomingEntries, type CalendarEntry, type CardBilling, type CardBillings } from "@/features/payment/model";
import { RECENT_TRANSACTION_COUNT, transactionKeys, useRecentTransactions } from "@/features/transaction/api/queries";
import { TransactionRow } from "@/features/transaction/components/TransactionRow";
import { useRefetchStaleOnFocus } from "@/hooks/use-refetch-stale-on-focus";
import { currentDateKey, currentMonthKey, formatMonthDay, parseKSTDateKey } from "@/lib/date";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

const TRANSACTIONS_ROUTE = "/transaction";
const PAYMENT_CALENDAR_ROUTE = "/payment/calendar";
/** 카드 청구 상세(PAGE-33, P1). 카드 행을 누르면 간다 */
const CARD_BILLING_ROUTE = "/payment/card-billing";
/** 수입 계좌 변경(IncomeAccountScreen 변경 모드). 온보딩 뒤 수입 계좌를 바꾸는 유일한 앱 내 진입점 (Pencil AMSKF, 2026-09-16) */
const INCOME_ACCOUNT_ROUTE = "/account/income";

/** 시안(UjYhB)은 2건을 보여 준다. 남은 건이 많아도 가까운 순으로 이만큼만 둔다 */
const UPCOMING_PAYMENT_LIMIT = 3;

type AssetTab = "accounts" | "cards";

const ASSET_TABS: { key: AssetTab; label: string }[] = [
  { key: "accounts", label: "계좌" },
  { key: "cards", label: "카드" },
];

// PAGE-11 자산 (Pencil 자산관리 UjYhB). 사용자 결정(2026-09-11): 대출 탭·송금 버튼은 KeyFin 명세에 없어 빼고,
// 햄버거는 자리만 두고 비활성, 정기결제 예정의 '관리'는 결제 캘린더(PAGE-24)로 간다.
// 계좌는 GET /accounts(잔액 스냅샷), 카드는 카드 API 가 없어 금융망 후보에서 온다 — 카드 탭을 열 때만 금융망을 부른다.
// 섹션마다 따로 불러와 한쪽이 실패해도 나머지는 보인다.
function AssetsScreen() {
  const router = useRouter();
  const [tab, setTab] = React.useState<AssetTab>("accounts");
  const accounts = useAccounts();
  // 잔액은 실시간이 아니라 서버가 갱신한 스냅샷이라 기준 시각을 함께 보여 준다 (사용자 결정 2026-09-12)
  const asOf = accounts.data ? balanceAsOfLabel(accounts.data) : null;
  const topInset = useHeaderlessTop();

  return (
    <Screen>
      {/* 위 여백은 스크롤 뷰가 아니라 바깥 View 에 준다(예산 탭과 같은 방식). 스크롤 뷰 style 의 padding 은 Android 에서 내용을 밀기만 하고
          스크롤 범위는 늘리지 않아 끝이 그만큼 잘렸다 (2026-09-22) */}
      <View className="flex-1" style={{ paddingTop: topInset }}>
      <ScreenScrollView className="flex-1" overlapHeader={false} contentContainerClassName="gap-10 pb-8">
      <View className="gap-4">
      {/* 예산 탭 TotalCard 와 같은 카드로 감싼다 (사용자 요청 2026-09-20). 면 구분은 카드 규칙대로 테두리 대신 그림자(다크는 테두리) */}
      <View className="px-6">
        <View className="gap-1 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
          <Text className="text-caption text-card-foreground">내 총 자산</Text>
          {accounts.isPending ? (
            <Skeleton className="h-11 w-48 rounded-md" />
          ) : (
            <Text className="text-amount-lg tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
              {accounts.data === undefined ? "—" : formatKRW(totalBalance(accounts.data))}
            </Text>
          )}
          {asOf === null ? null : <Text className="text-caption tabular-nums text-card-foreground">{asOf}</Text>}
        </View>
      </View>

      <View className="flex-row gap-2 px-6" accessibilityRole="tablist">
        {ASSET_TABS.map(({ key, label }) => (
          <Pressable
            key={key}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === key }}
            onPress={() => setTab(key)}
            className={cn("h-10 flex-1 items-center justify-center rounded-md", tab === key ? "bg-primary" : "bg-accent")}
          >
            <Text className={cn("text-label", tab === key ? "text-primary-foreground" : "text-card-foreground")}>{label}</Text>
          </Pressable>
        ))}
      </View>

      <View className="gap-3 px-6">
        <View className="flex-row items-center justify-between">
          <Text className="text-h3 text-foreground" accessibilityRole="header">
            {tab === "accounts" ? "입출금 계좌" : "카드"}
          </Text>
          {tab === "accounts" && accounts.data !== undefined && accounts.data.length > 0 ? (
            <Pressable accessibilityRole="link" accessibilityLabel="수입 계좌 변경" hitSlop={10} onPress={() => router.push(INCOME_ACCOUNT_ROUTE)}>
              <Text className="text-caption text-primary">수입 계좌 변경</Text>
            </Pressable>
          ) : null}
        </View>
        {tab === "accounts" ? (
          accounts.isPending ? (
            <AssetSkeleton />
          ) : accounts.isError ? (
            <InlineRetry message="계좌를 불러오지 못했어요." retrying={accounts.isFetching} onRetry={() => accounts.refetch()} />
          ) : (
            <AccountList accounts={accounts.data} />
          )
        ) : (
          <CardSection />
        )}
      </View>
      </View>

      <UpcomingPayments />
      <RecentTransactions />
      </ScreenScrollView>
      </View>
    </Screen>
  );
}

// Pencil AccountItem (w4jgr1): 흰 카드(tint 배경 위, 2026-09-16). 송금 버튼 대신 로고 타일과 마스킹 번호를 둔다.
// 별칭이 있으면 제목으로 올리고 은행명은 아래로 내린다. 수입 계좌에는 뱃지를 단다.
// 행을 누르면 그 계좌로 거른 거래 내역(GET /transactions?accountId=)으로 간다(사용자 요청 2026-09-23) —
// 은행별 상세 내역 API 는 백엔드가 따로 만들기로 해 나오면 목적지만 바꾼다.
function AccountList({ accounts }: { accounts: LinkedAccount[] }) {
  const router = useRouter();
  if (accounts.length === 0) {
    return <EmptyState icon={WalletMinimal} title="연결된 계좌가 없어요" className="py-6" />;
  }
  return (
    <View className="gap-2">
      {accounts.map((account) => (
        <Pressable
          key={account.accountId}
          onPress={() => router.push({ pathname: TRANSACTIONS_ROUTE, params: { accountId: String(account.accountId) } })}
          className="flex-row items-center gap-3 rounded-lg bg-card p-4 shadow shadow-black/10 active:opacity-80 dark:border dark:border-border dark:shadow-none"
          accessible
          accessibilityRole="button"
          accessibilityHint="이 계좌의 거래 내역을 엽니다"
          accessibilityLabel={[
            account.alias ?? account.bankName,
            account.isIncome ? "수입 계좌" : null,
            account.maskedNo,
            `잔액 ${formatKRW(account.balance)}`,
          ]
            .filter(Boolean)
            .join(", ")}
        >
          <BankLogoTile name={account.bankName} />
          <View className="flex-1 gap-0.5">
            <View className="flex-row items-center gap-1.5">
              <Text className="shrink text-h3 text-foreground" numberOfLines={1}>
                {account.alias ?? account.bankName}
              </Text>
              {account.isIncome ? (
                <Badge variant="secondary">
                  <Text>수입</Text>
                </Badge>
              ) : null}
            </View>
            <Text className="text-caption tabular-nums text-card-foreground" numberOfLines={1}>
              {account.alias === null ? account.maskedNo : `${account.bankName} · ${account.maskedNo}`}
            </Text>
          </View>
          <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
            {formatKRW(account.balance)}
          </Text>
          <Icon as={ChevronRight} size={18} className="text-card-foreground" />
        </Pressable>
      ))}
    </View>
  );
}

// 카드 이름·번호를 주는 API 가 없어 금융망 후보의 연결 카드를 쓰고, 금액은 GET /cards/billings 로 채운다(cardId 로 잇는다).
// 둘 다 이 섹션이 보일 때만 부른다. 청구 조회가 실패해도 카드 목록은 그대로 두고 금액 줄만 빠진다.
// 카드 행은 청구 요약이 없어도 눌러서 카드 청구 상세(PAGE-33)로 간다.
function CardSection() {
  const router = useRouter();
  const candidates = useLinkCandidates();
  const billings = useCardBillings();

  if (candidates.isPending) return <AssetSkeleton />;
  if (candidates.isError) {
    return <CandidatesErrorState error={candidates.error} retrying={candidates.isFetching} onRetry={() => candidates.refetch()} />;
  }
  return (
    <CardList
      cards={linkedCards(candidates.data)}
      billings={billings.data}
      onOpen={(cardId) => router.push(`${CARD_BILLING_ROUTE}/${cardId}`)}
    />
  );
}

type CardListProps = {
  cards: LinkedCard[];
  billings: CardBillings | undefined;
  onOpen: (cardId: number) => void;
};

function CardList({ cards, billings, onOpen }: CardListProps) {
  if (cards.length === 0) {
    return <EmptyState icon={CreditCard} title="연결된 카드가 없어요" className="py-6" />;
  }
  return (
    <View className="gap-2">
      {cards.map((card) => (
        <CardRow key={card.cardId} card={card} billing={findCardBilling(billings, card.cardId)} onPress={() => onOpen(card.cardId)} />
      ))}
    </View>
  );
}

type CardRowProps = {
  card: LinkedCard;
  billing: CardBilling | null;
  onPress: () => void;
};

function CardRow({ card, billing, onPress }: CardRowProps) {
  const estimated = billing === null ? null : `이번 주 ${formatKRW(billing.estimatedAmount)}`;
  const unpaid = billing?.statement?.status === "UNPAID" ? billing.statement : null;

  return (
    <Pressable
      className="flex-row items-center gap-3 rounded-lg bg-card p-4 active:opacity-70 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none"
      accessibilityRole="button"
      accessibilityLabel={[`${card.cardName} ${card.issuerName} ${card.maskedNo}`, estimated, unpaidLabel(unpaid)]
        .filter(Boolean)
        .join(", ")}
      accessibilityHint="카드 청구 내역을 봅니다"
      onPress={onPress}
    >
      <BankLogoTile name={card.issuerName} />
      <View className="flex-1 gap-0.5">
        <Text className="text-h3 text-foreground" numberOfLines={1}>
          {card.cardName}
        </Text>
        <Text className="text-caption tabular-nums text-card-foreground" numberOfLines={1}>
          {card.issuerName} · {card.maskedNo}
        </Text>
      </View>
      {billing === null ? null : (
        <View className="items-end gap-0.5">
          <Text className="text-label tabular-nums text-foreground" numberOfLines={1}>
            {formatKRW(billing.estimatedAmount)}
          </Text>
          <Text className="text-caption tabular-nums text-card-foreground" numberOfLines={1}>
            {billingCaption(billing)}
          </Text>
        </View>
      )}
      <Icon as={ChevronRight} size={18} className="text-card-foreground" />
    </Pressable>
  );
}

/** 오른쪽 금액은 이번 주기 승인 합계(확정 전)다. 출금일을 모르는 카드는 재연결이 필요하다고 알린다 */
function billingCaption(billing: CardBilling): string {
  if (billing.estimatedWithdrawalDate === null) return "출금일 확인 필요";
  return `${formatMonthDay(parseKSTDateKey(billing.estimatedWithdrawalDate))} 출금 예정`;
}

function unpaidLabel(statement: CardBilling["statement"]): string | null {
  return statement === null ? null : `청구서 ${formatKRW(statement.amount)} 미결제`;
}

// Pencil RecurringPayments (Csfwz). 데이터는 홈 캘린더와 같은 GET /payments/calendar 캐시를 쓴다.
// '관리'는 결제 캘린더(PAGE-24)가 생겨 2026-09-13 에 열었다.
function UpcomingPayments() {
  const router = useRouter();
  const calendar = usePaymentCalendar(currentMonthKey());
  const entries = calendar.data ? upcomingEntries(calendar.data, currentDateKey(), UPCOMING_PAYMENT_LIMIT) : [];

  return (
    <View className="gap-3 px-6">
      <View className="flex-row items-center justify-between">
        <Text className="text-h2 text-foreground" accessibilityRole="header">
          이번 달 정기결제 예정
        </Text>
        <Pressable accessibilityRole="link" accessibilityLabel="결제 캘린더 열기" hitSlop={10} onPress={() => router.push(PAYMENT_CALENDAR_ROUTE)}>
          <Text className="text-caption text-primary">관리</Text>
        </Pressable>
      </View>
      {calendar.isPending ? (
        <AssetSkeleton />
      ) : calendar.isError ? (
        <InlineRetry message="정기결제 일정을 불러오지 못했어요." retrying={calendar.isFetching} onRetry={() => calendar.refetch()} />
      ) : entries.length === 0 ? (
        <Text className="text-body-sm text-card-foreground">이번 달 남은 정기결제가 없어요.</Text>
      ) : (
        <View className="gap-2">
          {entries.map((entry) => (
            <PaymentRow key={entry.key} entry={entry} />
          ))}
        </View>
      )}
    </View>
  );
}

function PaymentRow({ entry }: { entry: CalendarEntry }) {
  const date = formatMonthDay(parseKSTDateKey(entry.date));
  const amount = entry.estimated ? `${formatKRW(entry.amount)} 예정` : formatKRW(entry.amount);

  return (
    <View className="flex-row items-center justify-between gap-3 py-2" accessible accessibilityLabel={`${entry.name} ${date} ${amount}`}>
      <View className="flex-1 flex-row items-center gap-3">
        <View className="h-9 w-9 items-center justify-center rounded-full bg-accent">
          <Icon as={calendarEntryIcon(entry)} size={18} className="text-primary" />
        </View>
        <View className="flex-1 gap-0.5">
          <Text className="text-h3 text-foreground" numberOfLines={1}>
            {entry.name}
          </Text>
          <Text className="text-caption text-card-foreground">{date}</Text>
        </View>
      </View>
      <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
        {amount}
      </Text>
    </View>
  );
}

// Pencil RecentTransactions (ToBBS): 이번 달 최근 3건 + 전체보기(거래 내역 화면).
function RecentTransactions() {
  const router = useRouter();
  const recent = useRecentTransactions(currentMonthKey());
  useRefetchStaleOnFocus(transactionKeys.all);

  return (
    <View className="gap-3 px-6">
      <View className="flex-row items-center justify-between">
        <Text className="text-h2 text-foreground" accessibilityRole="header">
          최근 거래 내역
        </Text>
        <Pressable accessibilityRole="link" accessibilityLabel="거래 내역 전체보기" hitSlop={10} onPress={() => router.push(TRANSACTIONS_ROUTE)}>
          <Text className="text-caption text-primary">전체보기</Text>
        </Pressable>
      </View>
      {recent.isPending ? (
        <View className="gap-2">
          {Array.from({ length: RECENT_TRANSACTION_COUNT }, (_, index) => (
            <Skeleton key={index} className="h-14 w-full rounded-md" />
          ))}
        </View>
      ) : recent.isError ? (
        <InlineRetry message="거래 내역을 불러오지 못했어요." retrying={recent.isFetching} onRetry={() => recent.refetch()} />
      ) : recent.data.items.length === 0 ? (
        <EmptyState icon={Receipt} title="이번 달 거래가 아직 없어요" className="py-6" />
      ) : (
        <View>
          {recent.data.items.map((transaction) => (
            <TransactionRow
              key={transaction.id}
              transaction={transaction}
              onPress={() => router.push(`${TRANSACTIONS_ROUTE}/${transaction.id}`)}
            />
          ))}
        </View>
      )}
    </View>
  );
}

type InlineRetryProps = {
  message: string;
  retrying: boolean;
  onRetry: () => void;
};

// 섹션 하나만 실패했을 때 그 자리에서 다시 부른다 (규칙 50: 일부 실패는 전체를 막지 않는다).
function InlineRetry({ message, retrying, onRetry }: InlineRetryProps) {
  return (
    <View className="flex-row items-center justify-between gap-3 rounded-lg bg-muted px-4 py-3" accessibilityLiveRegion="polite">
      <Text className="flex-1 text-body-sm text-card-foreground">{message}</Text>
      <Pressable accessibilityRole="button" accessibilityState={{ disabled: retrying }} disabled={retrying} hitSlop={10} onPress={onRetry}>
        <Text className={cn("text-label", retrying ? "text-card-foreground" : "text-primary")}>다시 시도</Text>
      </Pressable>
    </View>
  );
}

const SKELETON_ROWS = [1, 2];

function AssetSkeleton() {
  return (
    <View className="gap-2" accessible accessibilityLabel="불러오는 중">
      {SKELETON_ROWS.map((row) => (
        <Skeleton key={row} className="h-16 w-full rounded-lg" />
      ))}
    </View>
  );
}

export { AssetsScreen };
