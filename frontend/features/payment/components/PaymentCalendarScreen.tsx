import { useLocalSearchParams, useRouter } from "expo-router";
import { CalendarDays, ChevronLeft, ChevronRight, WifiOff } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { flattenTransfers, usePaymentCalendar, useTransfers } from "@/features/payment/api/queries";
import { calendarEntryIcon } from "@/features/payment/catalog";
import { CALENDAR_EMPTY_MESSAGE, ESTIMATED_SUFFIX } from "@/features/payment/components/CalendarPopover";
import {
  canOpenCardBilling,
  canOpenEntry,
  findTransferForEntry,
  groupEntriesByDate,
  isEditableEntry,
  parseCalendarMonth,
  preparationLabel,
  type CalendarDayGroup,
  type CalendarEntry,
  type PaymentCalendar,
  type Transfer,
} from "@/features/payment/model";
import { currentMonthKey, formatMonthDay, formatMonthKeyLabel, parseKSTDateKey, shiftMonthKey } from "@/lib/date";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

const HOME_ROUTE = "/";
const FIXED_EXPENSE_ROUTE = "/payment/fixed-expense";
const TRANSFER_ROUTE = "/payment/transfer";
const CARD_BILLING_ROUTE = "/payment/card-billing";

/** 부족 뱃지 아래 한 줄. 제안이 있는 항목에만 붙는다 (Pencil cSTvK Note) */
const TRANSFER_NOTE = "탭해서 결제 전에 옮겨요";

/** KeyFin 에서 고칠 수 없는 항목에 붙이는 설명. 카드 정기결제는 출금 계좌가 아니라 카드 대금으로 함께 나간다 */
const ENTRY_NOTES: Partial<Record<CalendarEntry["type"], string>> = {
  CARD_SUBSCRIPTION: "카드 대금으로 함께 나가요",
  CARD_BILL: "카드 청구",
};

/**
 * PAGE-24 결제 캘린더. GET /payments/calendar 의 날짜별 출금 예정을 달 단위로 보여준다 (FR-PAY-01·02).
 * 준비 상태(prepared·shortage)·estimated 는 서버 값이라 그대로 표시만 하고, 서버가 아직 계산하지 않았으면(null) 뱃지를 그리지 않는다 (규칙 80).
 * 고정지출 항목은 모두 눌러서 연다 — 직접 등록한 것(FIXED)은 수정 폼(PAGE-26), 카드 정기결제(CARD_SUBSCRIPTION)는 읽기 전용 상세.
 * 카드 청구(CARD_BILL)는 카드 청구 상세(PAGE-33)로 간다(P1, 2026-09-17).
 * 부족 항목에 승인 가능한 이체 제안이 있으면 뱃지가 이체 승인(PAGE-25)으로 가는 버튼이 된다 — 푸시(P1) 전까지 유일한 앱 내 진입점(2026-09-16).
 * 헤더의 '관리'는 고정지출 관리(PAGE-26B)로 간다.
 * 달력 격자 대신 날짜별 목록으로 만든다(응답이 날짜·항목 목록이고 한 달 건수가 적다).
 * Pencil PAGE-24 결제 캘린더 (LGaxv) · 빈 상태 (XGcYs) · 오류 (w5uuk) · 준비 상태 없음 (pfLbO).
 */
function PaymentCalendarScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const month = parseCalendarMonth(params.month, currentMonthKey());
  const calendar = usePaymentCalendar(month);
  // 이 달(대상 출금일 기준) 제안만 받는다 — 출금 건당 1건이라 첫 쪽(20건)에 다 들어온다. 못 받아도 캘린더는 그대로 보이고 뱃지만 눌리지 않는다.
  const transfers = useTransfers({ month });
  const groups = calendar.data ? groupEntriesByDate(calendar.data.entries) : [];

  return (
    <Screen>
      <ScreenHeader
        title="결제 캘린더"
        onBack={() => (router.canGoBack() ? router.back() : router.replace(HOME_ROUTE))}
        right={
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="고정지출 관리"
            hitSlop={10}
            className="min-h-touch justify-center active:opacity-70"
            onPress={() => router.push(FIXED_EXPENSE_ROUTE)}
          >
            <Text className="text-label text-primary">관리</Text>
          </Pressable>
        }
      />

      <MonthStepper month={month} onChange={(next) => router.setParams({ month: next })} />

      {calendar.isPending ? (
        <CalendarSkeleton />
      ) : calendar.data === undefined ? (
        <EmptyState
          icon={WifiOff}
          title="출금 일정을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => calendar.refetch(), disabled: calendar.isFetching }}
        />
      ) : (
        <ScreenFlatList
          overlapHeader={false}
          data={groups}
          keyExtractor={(group) => group.date}
          contentContainerClassName="gap-10 px-6 pb-8"
          refreshing={calendar.isRefetching}
          onRefresh={() => calendar.refetch()}
          ListHeaderComponent={<CalendarSummary calendar={calendar.data} />}
          ListEmptyComponent={
            <EmptyState
              icon={CalendarDays}
              title={CALENDAR_EMPTY_MESSAGE}
              description="고정지출을 등록하면 출금 예정일이 여기에 보여요."
              action={{ label: "고정지출 등록", onPress: () => router.push(`${FIXED_EXPENSE_ROUTE}/new`) }}
            />
          }
          renderItem={({ item }) => (
            <DayGroup
              group={item}
              transfers={flattenTransfers(transfers.data)}
              onSelect={(entry) => {
                if (canOpenEntry(entry)) router.push(`${FIXED_EXPENSE_ROUTE}/${entry.fixedExpenseId}`);
                else if (canOpenCardBilling(entry)) router.push(`${CARD_BILLING_ROUTE}/${entry.cardId}`);
              }}
              onOpenTransfer={(transfer) => router.push(`${TRANSFER_ROUTE}/${transfer.id}`)}
            />
          )}
        />
      )}
    </Screen>
  );
}

type MonthStepperProps = {
  month: string;
  onChange: (month: string) => void;
};

// 거래 내역(PAGE-11 전체보기)과 같은 월 스테퍼. 앞으로 나갈 출금이라 다음 달로도 넘어간다.
function MonthStepper({ month, onChange }: MonthStepperProps) {
  return (
    <View className="flex-row items-center justify-center gap-4 pb-3">
      <Pressable accessibilityRole="button" accessibilityLabel="이전 달" hitSlop={12} onPress={() => onChange(shiftMonthKey(month, -1))}>
        <Icon as={ChevronLeft} size={20} className="text-foreground" />
      </Pressable>
      <Text className="text-h3 tabular-nums text-foreground" accessibilityLiveRegion="polite">
        {formatMonthKeyLabel(month)}
      </Text>
      <Pressable accessibilityRole="button" accessibilityLabel="다음 달" hitSlop={12} onPress={() => onChange(shiftMonthKey(month, 1))}>
        <Icon as={ChevronRight} size={20} className="text-foreground" />
      </Pressable>
    </View>
  );
}

// 준비 상태를 서버가 아직 계산하지 않았으면 '모두 준비됐어요'를 쓰지 않는다 — 모르는 것을 준비됐다고 말하지 않는다.
function CalendarSummary({ calendar }: { calendar: PaymentCalendar }) {
  const count = calendar.entries.length;
  if (count === 0) return null;

  return (
    <View className="flex-row items-center justify-between pb-1" accessibilityLiveRegion="polite">
      <Text className="text-body-sm text-card-foreground">출금 예정 {count}건</Text>
      {calendar.shortageCount > 0 ? (
        <Text className="text-body-sm tabular-nums text-destructive">준비 부족 {calendar.shortageCount}건</Text>
      ) : calendar.preparationKnown ? (
        <Text className="text-body-sm text-positive">모두 준비됐어요</Text>
      ) : null}
    </View>
  );
}

type DayGroupProps = {
  group: CalendarDayGroup;
  /** 승인 가능한 이체 제안. 부족 항목에 짝이 있으면 뱃지가 이체 승인으로 가는 버튼이 된다 */
  transfers: Transfer[];
  onSelect: (entry: CalendarEntry) => void;
  onOpenTransfer: (transfer: Transfer) => void;
};

// 날짜 묶음 제목은 작은 회색 라벨이 아니라 text-h3 검정으로 둔다 (DESIGN.md 섹션 구분 규칙, 2026-09-15).
function DayGroup({ group, transfers, onSelect, onOpenTransfer }: DayGroupProps) {
  return (
    <View className="gap-3">
      <Text className="text-h3 text-foreground" accessibilityRole="header">
        {formatMonthDay(parseKSTDateKey(group.date))}
      </Text>
      <View className="gap-2">
        {group.entries.map((entry) => (
          <EntryCard
            key={entry.key}
            entry={entry}
            transfer={findTransferForEntry(transfers, entry)}
            onPress={() => onSelect(entry)}
            onOpenTransfer={onOpenTransfer}
          />
        ))}
      </View>
    </View>
  );
}

type EntryCardProps = {
  entry: CalendarEntry;
  /** 이 항목의 이체 제안. 없으면 뱃지는 표시만 한다 */
  transfer: Transfer | null;
  onPress: () => void;
  onOpenTransfer: (transfer: Transfer) => void;
};

const CARD_SURFACE = "rounded-lg bg-card shadow shadow-black/10 dark:border dark:border-border dark:shadow-none";

// 흰 배경에서 그림자만으로는 구분이 안 돼 자산 탭 계좌 항목처럼 연보라 면으로 둔다. 아이콘 타일은 그 위의 흰 원.
// 이체 제안이 있는 부족 항목은 뱃지가 셰브런 달린 버튼이 되고 아래에 한 줄 안내가 붙는다 (Pencil PAGE-24 · 이체 제안 cSTvK, 2026-09-16).
// 그때는 카드 본문 버튼과 뱃지 버튼을 형제로 둔다 — 버튼 안에 버튼을 넣으면 웹에서 <button> 이 중첩돼 React 가 경고한다(2026-09-23).
// 뱃지 줄 앞에 아이콘 폭만큼 빈 칸을 둬 뱃지가 이름 아래에 맞춰 보이게 한다.
function EntryCard({ entry, transfer, onPress, onOpenTransfer }: EntryCardProps) {
  const openable = canOpenEntry(entry) || canOpenCardBilling(entry);
  const hint = entryHint(entry);
  const name = entry.estimated ? `${entry.name} ${ESTIMATED_SUFFIX}` : entry.name;
  const amount = formatKRW(entry.amount);
  const badge = preparationLabel(entry.preparation);
  const prepared = entry.preparation?.status === "PREPARED";
  const note = ENTRY_NOTES[entry.type] ?? null;
  const linkedTransfer = badge !== null ? transfer : null;
  const label = [`${name} ${amount}`, note, linkedTransfer ? null : badge].filter((part) => part !== null).join(", ");

  const body = (
    <Pressable
      className={cn("flex-row items-center gap-3 p-4 active:opacity-70", linkedTransfer ? "pb-2" : CARD_SURFACE)}
      accessibilityRole={openable ? "button" : undefined}
      accessibilityLabel={label}
      accessibilityHint={hint}
      disabled={!openable}
      onPress={onPress}
    >
      <View className="h-10 w-10 items-center justify-center rounded-full bg-accent">
        <Icon as={calendarEntryIcon(entry)} size={20} className="text-primary" />
      </View>
      <View className="flex-1 gap-1">
        <Text className="text-h3 text-foreground" numberOfLines={1}>
          {name}
        </Text>
        {(linkedTransfer ? null : badge) === null && note === null ? null : (
          <View className="flex-row flex-wrap items-center gap-2">
            {badge === null || linkedTransfer ? null : (
              <View className={cn("rounded-sm px-1.5 py-0.5", prepared ? "bg-positive-muted" : "bg-destructive-muted")}>
                <Text className={cn("text-caption tabular-nums", prepared ? "text-positive" : "text-destructive")}>{badge}</Text>
              </View>
            )}
            {note === null ? null : <Text className="text-caption text-card-foreground">{note}</Text>}
          </View>
        )}
      </View>
      <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
        {amount}
      </Text>
      {openable ? <Icon as={ChevronRight} size={18} className="text-card-foreground" /> : null}
    </Pressable>
  );

  if (!linkedTransfer || badge === null) return body;

  return (
    <View className={CARD_SURFACE}>
      {body}
      <View className="flex-row gap-3 px-4 pb-4">
        <View className="w-10" />
        <View className="flex-1 items-start gap-1">
          <Pressable
            className="flex-row items-center gap-0.5 rounded-sm bg-destructive-muted py-0.5 pl-1.5 pr-1 active:opacity-70"
            accessibilityRole="button"
            accessibilityLabel={`${badge}, 이체 제안 보기`}
            accessibilityHint="결제 전에 부족한 금액을 옮기는 화면을 엽니다"
            hitSlop={6}
            onPress={() => onOpenTransfer(linkedTransfer)}
          >
            <Text className="text-caption tabular-nums text-destructive">{badge}</Text>
            <Icon as={ChevronRight} size={14} className="text-destructive" />
          </Pressable>
          <Text className="text-caption text-card-foreground">{TRANSFER_NOTE}</Text>
        </View>
      </View>
    </View>
  );
}

function entryHint(entry: CalendarEntry): string | undefined {
  if (canOpenCardBilling(entry)) return "카드 청구 내역을 봅니다";
  if (!canOpenEntry(entry)) return undefined;
  return isEditableEntry(entry) ? "고정지출을 수정합니다" : "카드 정기결제 정보를 봅니다";
}

const SKELETON_ROWS = [1, 2, 3];

function CalendarSkeleton() {
  return (
    <View className="gap-3 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      {SKELETON_ROWS.map((row) => (
        <Skeleton key={row} className="h-20 w-full rounded-2xl" />
      ))}
    </View>
  );
}

export { PaymentCalendarScreen };
