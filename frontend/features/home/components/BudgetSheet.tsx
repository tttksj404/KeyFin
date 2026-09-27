import type { UseQueryResult } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { ChevronRight, X } from "lucide-react-native";
import { Pressable, ScrollView, useWindowDimensions, View } from "react-native";

import { Button } from "@/components/ui/button";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { budgetPeriodLabel, envelopeHealth, usedBarPercent, type Budget, type BudgetEnvelope, type EnvelopeHealth } from "@/features/budget/model";
import { BudgetCard } from "@/features/home/components/BudgetCard";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

export const BUDGET_SHEET_CLOSE_LABEL = "보드 닫기";
export const BUDGET_SHEET_LINK_LABEL = "예산 탭에서 자세히";
export const BUDGET_SHEET_ERROR_TITLE = "예산을 불러오지 못했어요";
const BUDGET_ROUTE = "/budget";
/**
 * 시트 높이(화면 비율). 내용 길이와 무관하게 이만큼 위로 올라오고, 내용이 더 길면 안에서 스크롤한다.
 * 0.8 최대 높이만 두던 것을 고정 높이로 바꿔 시트를 위로 키웠다 (사용자 요청 2026-09-23).
 */
const SHEET_HEIGHT_RATIO = 0.9;

const FILL_CLASS: Record<EnvelopeHealth, string> = {
  good: "bg-positive",
  warning: "bg-warning",
  over: "bg-destructive",
  unset: "bg-muted",
};

type BudgetSheetProps = {
  visible: boolean;
  /** 조회 상태째 받는다 — 시트 안에서 불러오는 중·실패(재시도)까지 보여준다 */
  budget: UseQueryResult<Budget>;
  onClose: () => void;
};

/**
 * 벽의 리스트(보드)를 탭하면 아래서 올라오는 예산 시트 (FR-BGT-04). 홈에서 예산 카드를 빼고 방을 키우면서
 * 예산 정보는 전부 여기로 옮겼다(사용자 결정 2026-09-15): 예산 카드(총액·사용률·봉투 7종 막대) + 봉투별 잔액 + 예산 탭 링크.
 * 봉투 막대를 누르면 봉투 상세(PAGE-23)로 간다. 미확정 정리 시트(SubcategorySheet)와 같은 RN Modal 방식이다.
 * Pencil home/p0/board-open (KQLga) 의 시트 (2026-09-15 팝오버에서 바꿈).
 * 시트 머리에 있던 "9월 1일~30일 예산 보드 · n원 남음" 제목·부제목은 바로 아래 예산 카드의 "남은 예산 · 기간 · 금액" 과 겹쳐 뺐다
 * (사용자 요청 2026-09-23) — 닫기 버튼만 오른쪽 위에 남긴다.
 */
function BudgetSheet({ visible, budget, onClose }: BudgetSheetProps) {
  const router = useRouter();
  const window = useWindowDimensions();
  const open = (href: string) => {
    onClose();
    router.push(href);
  };
  const sheetHeight = window.height * SHEET_HEIGHT_RATIO;

  return (
    <BottomSheet visible={visible} onClose={onClose} closeLabel={BUDGET_SHEET_CLOSE_LABEL}>
        <View style={{ height: sheetHeight }}>
          <View className="flex-row items-center justify-end px-5 pt-2">
            <Pressable accessibilityRole="button" accessibilityLabel="닫기" onPress={onClose} hitSlop={8} className="h-touch w-touch items-center justify-center">
              <Icon as={X} size={20} className="text-card-foreground" />
            </Pressable>
          </View>
          <ScrollView contentContainerClassName="gap-5 px-5 pb-8">
            <SheetBody budget={budget} onSelectEnvelope={(envelopeId) => open(`${BUDGET_ROUTE}/${envelopeId}`)} />
            {budget.data ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={BUDGET_SHEET_LINK_LABEL}
                onPress={() => open(BUDGET_ROUTE)}
                className="flex-row items-center gap-1 self-start active:opacity-70"
                hitSlop={8}
              >
                <Text className="text-label text-primary">{BUDGET_SHEET_LINK_LABEL}</Text>
                <Icon as={ChevronRight} size={14} className="text-primary" />
              </Pressable>
            ) : null}
          </ScrollView>
        </View>
    </BottomSheet>
  );
}

type SheetBodyProps = {
  budget: UseQueryResult<Budget>;
  onSelectEnvelope: (envelopeId: number) => void;
};

// 예산만 실패해도 방은 그대로 두고 시트 안에서 재시도한다 (규칙 50 일부 실패 대응).
function SheetBody({ budget, onSelectEnvelope }: SheetBodyProps) {
  if (budget.isPending) {
    return (
      <View className="gap-3" accessible accessibilityLabel="예산 불러오는 중">
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-5 w-3/4" />
      </View>
    );
  }
  if (budget.isError) {
    return (
      <View className="items-center gap-3 py-4" accessibilityLiveRegion="polite">
        <Text className="text-h3 text-foreground">{BUDGET_SHEET_ERROR_TITLE}</Text>
        <Button variant="secondary" className="h-button-md rounded-lg px-6" disabled={budget.isFetching} onPress={() => budget.refetch()}>
          <Text>다시 시도</Text>
        </Button>
      </View>
    );
  }
  // 확정 전(PROPOSED)은 홈이 확정 화면으로 보내므로 여기까지 total 이 없는 건 모르는 상태(UNKNOWN)뿐이다.
  if (budget.data.total === null) {
    return <Text className="text-body-sm text-card-foreground">예산을 승인하면 봉투별 잔액이 여기에 보여요.</Text>;
  }
  return (
    <>
      <BudgetCard total={budget.data.total} envelopes={budget.data.envelopes} period={budgetPeriodLabel(budget.data)} onSelectEnvelope={onSelectEnvelope} />
      <View className="gap-2">
        <Text className="text-h3 text-foreground" accessibilityRole="header">
          봉투별 남은 금액
        </Text>
        {budget.data.envelopes.map((envelope) => (
          <EnvelopeRow key={envelope.envelopeId} envelope={envelope} />
        ))}
      </View>
    </>
  );
}

// 확정액 0 인 봉투는 잔여율이 없어 빈 트랙이고, 쓴 돈이 있으면 over 색으로 초과 금액을 적는다(사용자 결정 2026-09-12).
// 막대는 6 → 12pt (사용자 요청 2026-09-23, 시트를 키우며 두 배).
function EnvelopeRow({ envelope }: { envelope: BudgetEnvelope }) {
  const health = envelopeHealth(envelope);
  const barPercent = usedBarPercent(envelope.remainingRate);
  const remainingText =
    envelope.remaining === null ? "-" : health === "over" ? `초과 ${formatKRW(envelope.remaining, { sign: "never" })}` : formatKRW(envelope.remaining);

  return (
    <View className="flex-row items-center gap-3" accessible accessibilityLabel={`${envelope.name} ${remainingText} 남음`}>
      <Text className="w-20 text-label text-foreground" numberOfLines={1}>
        {envelope.name}
      </Text>
      <View className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
        <View className={cn("h-full rounded-full", FILL_CLASS[health])} style={{ width: `${barPercent}%` }} />
      </View>
      <Text className={cn("w-24 text-right text-label tabular-nums", health === "over" ? "text-destructive" : "text-foreground")}>{remainingText}</Text>
    </View>
  );
}

export { BudgetSheet };
export type { BudgetSheetProps };
