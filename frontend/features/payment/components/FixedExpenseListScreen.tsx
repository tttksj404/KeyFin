import { useRouter } from "expo-router";
import { CalendarClock, ChevronRight, Plus, WifiOff } from "lucide-react-native";
import { Pressable, RefreshControl, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useFixedExpenses } from "@/features/payment/api/queries";
import { expenseTypeIcon, expenseTypeLabel } from "@/features/payment/catalog";
import { paymentDayLabel, splitFixedExpenses, type FixedExpense } from "@/features/payment/model";
import { formatKRW } from "@/lib/money";

const PAYMENT_CALENDAR_ROUTE = "/payment/calendar";
const FIXED_EXPENSE_ROUTE = "/payment/fixed-expense";
/** 자동 감지 카드 청구는 금액이 null 이다(청구서로 엔진이 계산) */
const BILL_AMOUNT_LABEL = "청구서 기준";

/**
 * PAGE-26B 고정지출 관리 (FR-PAY-07). GET /fixed-expenses 의 활성 고정지출을 등록 순으로 보여준다.
 * 모든 항목을 눌러서 연다 — 직접 등록한 항목은 수정(PAGE-26), 금융망에서 동기화한 카드 정기결제(synced)는
 * 수정·삭제가 409(PAY_002)라 읽기 전용 상세로 간다(사용자 결정 2026-09-15: 한 묶음만 눌리지 않으면 통일감이 깨진다).
 * 날짜별 출금 예정은 결제 캘린더(PAGE-24)가 맡는다. 진입은 결제 캘린더 헤더의 '관리'.
 * Pencil PAGE-26B 고정지출 관리 (mtr9c) · 빈 상태 (riWW2) · 오류 (dETNH).
 */
function FixedExpenseListScreen() {
  const router = useRouter();
  const expenses = useFixedExpenses();
  const openCreate = () => router.push(`${FIXED_EXPENSE_ROUTE}/new`);

  return (
    <Screen>
      <ScreenHeader
        title="고정지출 관리"
        onBack={() => (router.canGoBack() ? router.back() : router.replace(PAYMENT_CALENDAR_ROUTE))}
        right={
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="고정지출 등록"
            hitSlop={10}
            className="h-touch w-touch items-center justify-center active:opacity-70"
            onPress={openCreate}
          >
            <Icon as={Plus} size={24} className="text-foreground" />
          </Pressable>
        }
      />

      {expenses.isPending ? (
        <ListSkeleton />
      ) : expenses.data === undefined ? (
        <EmptyState
          icon={WifiOff}
          title="고정지출을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => expenses.refetch(), disabled: expenses.isFetching }}
        />
      ) : expenses.data.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title="등록한 고정지출이 없어요"
          description="월세·공과금처럼 매달 나가는 돈을 등록하면 결제 캘린더에 출금일이 보여요."
          action={{ label: "고정지출 등록", onPress: openCreate }}
        />
      ) : (
        <ScreenScrollView
          contentContainerClassName="gap-10 px-6 pb-8"
          refreshControl={<RefreshControl refreshing={expenses.isRefetching} onRefresh={() => expenses.refetch()} />}
        >
          <FixedExpenseSections expenses={expenses.data} onSelect={(id) => router.push(`${FIXED_EXPENSE_ROUTE}/${id}`)} />
        </ScreenScrollView>
      )}
    </Screen>
  );
}

type FixedExpenseSectionsProps = {
  expenses: FixedExpense[];
  onSelect: (id: number) => void;
};

// 섹션은 자산 탭처럼 나눈다: 제목 text-h2 검정, 섹션 사이 32 · 제목과 목록 사이 12 (DESIGN.md 섹션 구분 규칙, 2026-09-15).
function FixedExpenseSections({ expenses, onSelect }: FixedExpenseSectionsProps) {
  const { manual, synced } = splitFixedExpenses(expenses);

  return (
    <>
      {manual.length === 0 ? null : (
        <View className="gap-3">
          <SectionTitle title="직접 등록" count={manual.length} />
          <View className="gap-2">
            {manual.map((expense) => (
              <ExpenseRow key={expense.id} expense={expense} hint="고정지출을 수정합니다" onPress={() => onSelect(expense.id)} />
            ))}
          </View>
        </View>
      )}
      {synced.length === 0 ? null : (
        <View className="gap-3">
          <View className="gap-1">
            <SectionTitle title="카드 정기결제" count={synced.length} />
            <Text className="text-body-sm text-card-foreground">
              카드사에서 불러온 항목이라 카드 대금으로 함께 나가요. 바꾸거나 해지하려면 카드사·서비스에서 해 주세요.
            </Text>
          </View>
          <View className="gap-2">
            {synced.map((expense) => (
              <ExpenseRow key={expense.id} expense={expense} hint="카드 정기결제 정보를 봅니다" onPress={() => onSelect(expense.id)} />
            ))}
          </View>
        </View>
      )}
    </>
  );
}

function SectionTitle({ title, count }: { title: string; count: number }) {
  return (
    <Text className="text-h2 tabular-nums text-foreground" accessibilityRole="header">
      {title} {count}건
    </Text>
  );
}

function amountLabel(expense: FixedExpense): string {
  return expense.amount === null ? BILL_AMOUNT_LABEL : formatKRW(expense.amount);
}

function detailLabel(expense: FixedExpense): string {
  const parts = [expenseTypeLabel(expense.expenseType), paymentDayLabel(expense.paymentDay)];
  if (expense.isVariable) parts.push("예상액");
  return parts.join(" · ");
}

type ExpenseRowProps = {
  expense: FixedExpense;
  hint: string;
  onPress: () => void;
};

// 흰 배경에서 그림자만으로는 구분이 안 돼 자산 탭 계좌 항목처럼 연보라 면으로 둔다. 아이콘 타일은 그 위의 흰 원.
function ExpenseRow({ expense, hint, onPress }: ExpenseRowProps) {
  const amount = amountLabel(expense);
  const detail = detailLabel(expense);

  return (
    <Pressable
      className="flex-row items-center gap-3 rounded-lg bg-card p-4 active:opacity-70 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none"
      accessibilityRole="button"
      accessibilityLabel={`${expense.name} ${amount}, ${detail}`}
      accessibilityHint={hint}
      onPress={onPress}
    >
      <View className="h-10 w-10 items-center justify-center rounded-full bg-accent">
        <Icon as={expenseTypeIcon(expense.expenseType)} size={20} className="text-primary" />
      </View>
      <View className="flex-1 gap-0.5">
        <Text className="text-h3 text-foreground" numberOfLines={1}>
          {expense.name}
        </Text>
        <Text className="text-caption text-card-foreground" numberOfLines={1}>
          {detail}
        </Text>
      </View>
      <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
        {amount}
      </Text>
      <Icon as={ChevronRight} size={18} className="text-card-foreground" />
    </Pressable>
  );
}

const SKELETON_ROWS = [1, 2, 3];

function ListSkeleton() {
  return (
    <View className="gap-3 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      {SKELETON_ROWS.map((row) => (
        <Skeleton key={row} className="h-20 w-full rounded-lg" />
      ))}
    </View>
  );
}

export { FixedExpenseListScreen };
