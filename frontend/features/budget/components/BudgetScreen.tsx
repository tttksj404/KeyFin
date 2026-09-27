import type { UseQueryResult } from "@tanstack/react-query";
import { Redirect, useRouter } from "expo-router";
import { CircleAlert, WalletMinimal, WifiOff } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";

import { AmountInput } from "@/components/ui/amount-input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { CountUpAmount } from "@/components/ui/count-up-amount";
import { FillBar } from "@/components/ui/fill-bar";
import { Icon } from "@/components/ui/icon";
import { KeyboardAvoidingView } from "@/components/ui/keyboard-avoiding-view";
import { Screen, ScreenScrollView, useHeaderlessTop } from "@/components/ui/screen";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { needsConfirmation, useCurrentBudget, useUpdateEmergencyFund } from "@/features/budget/api/queries";
import { EnvelopeCarousel } from "@/features/budget/components/EnvelopeCarousel";
import { PROPOSAL_FROM_HOME_HREF } from "@/features/budget/components/BudgetProposalScreen";
import { emergencyFundErrorMessage } from "@/features/budget/errors";
import {
  budgetHealth,
  budgetPeriodLabel,
  emergencyAmountError,
  envelopeHealth,
  isEmergencyDirty,
  toEmergencyFundRequest,
  toEmergencyInput,
  usedBarPercent,
  type Budget,
  type BudgetEmergency,
  type BudgetEnvelope,
  type BudgetHealth,
  type BudgetTotal,
  type EnvelopeHealth,
} from "@/features/budget/model";
import { compareKRW, formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

/** 봉투 행 탭 → 봉투 상세(PAGE-23) */
const ENVELOPE_DETAIL_ROUTE = "/budget";
const FROM_ENVELOPE = "envelope";

// Pencil budget (kvc1e). 확정 전(PROPOSED) 주기는 이 탭 대신 예산 확정 화면으로 보낸다(노션 예산·잔액 조회, 사용자 결정 2026-09-12).
function BudgetScreen() {
  const budget = useCurrentBudget();
  const topInset = useHeaderlessTop();

  if (needsConfirmation(budget)) return <Redirect href={PROPOSAL_FROM_HOME_HREF} />;

  return (
    <Screen>
      <View className="flex-1" style={{ paddingTop: topInset }}>
        <BudgetContent budget={budget} />
      </View>
    </Screen>
  );
}

type BudgetContentProps = {
  budget: UseQueryResult<Budget>;
};

// Pencil Content (U133b / AptUM): 좌우 여백 24 · 블록 간격 20.
function BudgetContent({ budget }: BudgetContentProps) {
  const router = useRouter();

  if (budget.isPending) return <BudgetSkeleton />;
  if (budget.isError) {
    return (
      <EmptyState
        icon={WifiOff}
        title="예산을 불러오지 못했어요"
        description="연결 상태를 확인한 뒤 다시 시도해 주세요."
        action={{ label: "다시 시도", onPress: () => budget.refetch(), disabled: budget.isFetching }}
      />
    );
  }

  const { total, envelopes } = budget.data;

  return (
    // 비상금 금액 입력이 화면 아래쪽에 있어 키패드가 덮지 않게 밀어 올린다
    <KeyboardAvoidingView className="flex-1">
    <ScreenScrollView className="flex-1" contentContainerClassName="flex-grow gap-10 px-6" keyboardShouldPersistTaps="handled">
      {/* 총액 카드 바로 아래에 회전판이 온다 — 하단에 붙어 있던 회전판과 비상금의 위아래를 바꿨다(사용자 요청 2026-09-23) */}
      {total === null ? null : <TotalCard total={total} period={budgetPeriodLabel(budget.data)} />}
      <View className="gap-4">
        <SectionTitle heading="봉투별 잔액" count={envelopes.length} />
        {envelopes.length === 0 ? (
          <EmptyState icon={WalletMinimal} title="봉투가 아직 없어요" description="예산이 만들어지면 봉투 7종이 여기에 보여요." />
        ) : (
          // 좌우로 돌리는 원판이라 화면 폭을 다 써야 옆 카드가 끝에 걸쳐 보인다 — 본문 좌우 여백을 상쇄한다.
          <View className="-mx-6">
            <EnvelopeCarousel
              envelopes={envelopes}
              // 봉투가 펼쳐져 화면을 덮은 뒤 넘어가므로 스택 전환 애니메이션은 끈다(from=envelope)
              onSelect={(envelopeId) => router.push(`${ENVELOPE_DETAIL_ROUTE}/${envelopeId}?from=${FROM_ENVELOPE}`)}
            />
          </View>
        )}
      </View>
      {/* 비상금은 봉투 밖에서 쓰는 돈이라 맨 아래에 둔다. 남는 높이는 위에 몰아 비상금이 화면 바닥 쪽에 붙는다.
          탭 바에 너무 붙어 보여 아래 여백을 32 둔다(사용자 요청 2026-09-23) */}
      <View className="flex-grow justify-end pb-8">
        <EmergencySection budgetId={budget.data.budgetId} emergency={budget.data.emergency} />
      </View>
    </ScreenScrollView>
    </KeyboardAvoidingView>
  );
}

// Pencil TotalCard (aAfOZ) 의 Used 막대는 $primary 한 가지뿐이라 경고·초과 색은 홈 BudgetCard 와 같은 기준으로 맞췄다.
type EmergencySectionProps = {
  budgetId: number;
  emergency: BudgetEmergency;
};

/**
 * 비상금 가상 풀 (FR-BGT-09, P1). 봉투 밖에서 따로 쓰는 돈이라 회전판 아래, 화면 맨 아래에 둔다(2026-09-23 회전판과 자리 바꿈).
 * 실제 계좌가 아니고 봉투 잔액·이체에 영향을 주지 않아 확인 창 없이 저장 버튼만 둔다.
 * 사용액은 주기 안 EMERGENCY 태그 거래 합(서버 값)이고, 넘겨 쓰면 남은 금액이 음수가 된다.
 */
function EmergencySection({ budgetId, emergency }: EmergencySectionProps) {
  const update = useUpdateEmergencyFund();
  const [amount, setAmount] = useState(() => toEmergencyInput(emergency));

  const invalidReason = emergencyAmountError(amount);
  const dirty = isEmergencyDirty(amount, emergency);
  const canSave = dirty && invalidReason === null && !update.isPending;
  const isSet = compareKRW(emergency.amount, "0") > 0;
  const overspent = compareKRW(emergency.remaining, "0") < 0;

  const save = () => {
    if (!canSave) return;
    update.mutate(
      { budgetId, request: toEmergencyFundRequest(amount) },
      { onSuccess: (fund) => setAmount(toEmergencyInput(fund.emergency)) }
    );
  };

  return (
    <View className="gap-4 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
      <View className="gap-1">
        <Text className="text-label text-card-foreground">비상금</Text>
        {isSet ? (
          <>
            <Text
              className={cn("text-amount-sm tabular-nums", overspent ? "text-destructive" : "text-foreground")}
              maxFontSizeMultiplier={1.3}
            >
              {formatKRW(emergency.remaining)}
            </Text>
            <Text className="text-caption tabular-nums text-card-foreground">
              설정 {formatKRW(emergency.amount)} · 사용 {formatKRW(emergency.spent)}
            </Text>
          </>
        ) : (
          <Text className="text-body-sm text-card-foreground">
            정해 두면 갑작스러운 지출을 봉투와 따로 관리할 수 있어요. 거래를 정리할 때 비상금으로 표시한 금액이 여기서 빠져요.
          </Text>
        )}
      </View>

      <AmountInput
        variant="field"
        className="h-input rounded-lg"
        value={amount}
        onChangeValue={setAmount}
        editable={!update.isPending}
        accessibilityLabel="비상금 금액"
      />
      <Text className="text-caption text-card-foreground">1,000원 단위로 정하고, 0원으로 두면 비상금을 쓰지 않아요.</Text>

      {update.isError ? (
        <View className="flex-row items-center gap-1.5" accessibilityLiveRegion="polite">
          <Icon as={CircleAlert} size={16} className="text-destructive" />
          <Text className="shrink text-caption text-destructive">{emergencyFundErrorMessage(update.error)}</Text>
        </View>
      ) : null}
      {invalidReason === null ? null : <Text className="text-caption text-card-foreground">{invalidReason}</Text>}

      <Button
        className="h-button-md rounded-lg"
        disabled={!canSave}
        accessibilityState={{ disabled: !canSave }}
        accessibilityLabel="비상금 저장"
        onPress={save}
      >
        <Text>{update.isPending ? "저장하는 중" : "비상금 저장"}</Text>
      </Button>
    </View>
  );
}

const TOTAL_BAR_CLASS: Record<BudgetHealth, string> = {
  good: "bg-primary",
  warning: "bg-warning",
  over: "bg-destructive",
};

type TotalCardProps = {
  total: BudgetTotal;
  /** 현재 주기 "9월 1일~30일" */
  period: string;
};

// Pencil PAGE-12 예산 탭 (kvc1e) 의 TotalCard: 흰 카드 안에 라벨 · 금액 · 진행 바 8pt · 총/사용 (2026-09-17 사용자 결정 — IiOk3 의 카드 없는 안에서 되돌림).
// 면 구분은 카드 규칙대로 테두리 대신 그림자(다크는 테두리).
function TotalCard({ total, period }: TotalCardProps) {
  const health = budgetHealth(total);
  const used = usedBarPercent(total.remainingRate);

  return (
    <View className="gap-3 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
      <Text className="text-label tabular-nums text-card-foreground">{period} 남은 예산</Text>
      <CountUpAmount
        value={total.remaining}
        className={cn("text-amount-lg tabular-nums", health === "over" ? "text-destructive" : "text-foreground")}
      />
      <FillBar
        percent={used}
        fillClassName={TOTAL_BAR_CLASS[health]}
        fillDelay={0}
        accessible
        accessibilityRole="progressbar"
        accessibilityLabel="예산 사용률"
        accessibilityValue={{ min: 0, max: 100, now: used }}
      />
      <View className="flex-row justify-between">
        <Text className="text-caption tabular-nums text-card-foreground">총 {formatKRW(total.confirmed)}</Text>
        <Text className="text-caption tabular-nums text-card-foreground">사용 {formatKRW(total.spent)}</Text>
      </View>
    </View>
  );
}

type SectionTitleProps = {
  heading: string;
  count: number;
};

// Pencil SectionTitle (XcJHm / Ce47c)
function SectionTitle({ heading, count }: SectionTitleProps) {
  return (
    <View className="flex-row items-center justify-between">
      <Text className="text-h3 text-foreground" accessibilityRole="header">
        {heading}
      </Text>
      <Text className="text-caption tabular-nums text-card-foreground">{count}개</Text>
    </View>
  );
}

const SKELETON_ROWS = [1, 2, 3, 4, 5, 6, 7];

function BudgetSkeleton() {
  return (
    <View className="gap-5 px-6" accessible accessibilityLabel="불러오는 중">
      <View className="gap-3">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-11 w-48" />
        <Skeleton className="h-2 w-full rounded-full" />
      </View>
      <Skeleton className="h-6 w-24" />
      <View className="gap-4">
        {SKELETON_ROWS.map((row) => (
          <View key={row} className="gap-2">
            <Skeleton className="h-7 w-full" />
            <Skeleton className="h-1.5 w-full rounded-full" />
          </View>
        ))}
      </View>
    </View>
  );
}

export { BudgetScreen };
