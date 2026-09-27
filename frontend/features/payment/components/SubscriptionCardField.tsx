import { Check, ChevronRight, CircleAlert, X } from "lucide-react-native";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useAssignFixedExpenseCard, useCardBillings } from "@/features/payment/api/queries";
import { fixedExpenseCardErrorMessage } from "@/features/payment/errors";
import type { CardBilling, FixedExpense } from "@/features/payment/model";
import { cn } from "@/lib/utils";

const TITLE = "결제 카드";
const UNASSIGNED_LABEL = "지정하기";

/**
 * 카드 정기결제 상세의 "결제 카드" 행과 카드 선택 시트 (-184, 사용자 결정 2026-09-24).
 * 금융망 정기결제 조회에는 결제 카드가 없어(-183) 카드가 여러 장이면 사용자가 한 번 고른다 — 고른 카드는 코칭 예측에 쓰인다.
 * 카드 목록은 GET /cards/billings 의 관리 카드를 쓴다. 고르면 PATCH /fixed-expenses/{id}/card 뒤 시트를 닫는다.
 */
function SubscriptionCardField({ expense }: { expense: FixedExpense }) {
  const [open, setOpen] = useState(false);
  const cards = useCardBillings();
  const assign = useAssignFixedExpenseCard();
  const current = cards.data?.cards.find((card) => card.cardId === expense.cardId) ?? null;
  const label = expense.cardId === null ? UNASSIGNED_LABEL : (current?.cardName ?? "");

  const openSheet = () => {
    assign.reset();
    setOpen(true);
  };
  const select = (cardId: number) => {
    if (cardId === expense.cardId) {
      setOpen(false);
      return;
    }
    assign.mutate({ id: expense.id, cardId }, { onSuccess: () => setOpen(false) });
  };

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${TITLE} ${expense.cardId === null ? "미지정" : label}`}
        accessibilityHint="결제 카드를 고르는 창을 엽니다"
        onPress={openSheet}
        className="flex-row items-center justify-between gap-3 border-b border-border py-3.5 active:opacity-70"
      >
        <Text className="text-caption text-card-foreground">{TITLE}</Text>
        <View className="shrink flex-row items-center gap-1">
          <Text className={cn("shrink text-body-sm", expense.cardId === null ? "text-primary" : "text-foreground")} numberOfLines={1}>
            {label}
          </Text>
          <Icon as={ChevronRight} size={16} className="text-card-foreground" />
        </View>
      </Pressable>

      <BottomSheet visible={open} onClose={() => setOpen(false)} closeLabel={`${TITLE} 선택 닫기`}>
        <View className="flex-row items-center justify-between px-5 pt-5">
          <Text className="text-h3 text-popover-foreground" accessibilityRole="header">
            {TITLE}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="닫기"
            onPress={() => setOpen(false)}
            hitSlop={8}
            className="h-touch w-touch items-center justify-center"
          >
            <Icon as={X} size={20} className="text-card-foreground" />
          </Pressable>
        </View>
        <ScrollView className="max-h-96" contentContainerClassName="gap-2 px-5 pb-8 pt-2">
          {cards.isPending ? (
            <Skeleton className="h-touch w-full rounded-md" />
          ) : cards.data === undefined || cards.data.cards.length === 0 ? (
            <Text className="py-4 text-body-sm text-card-foreground">
              {cards.data === undefined ? "카드 목록을 불러오지 못했어요." : "연결된 카드가 없어요."}
            </Text>
          ) : (
            cards.data.cards.map((card) => (
              <CardOption
                key={card.cardId}
                card={card}
                selected={card.cardId === expense.cardId}
                disabled={assign.isPending}
                onPress={() => select(card.cardId)}
              />
            ))
          )}
          {assign.isError ? (
            <View className="flex-row items-center gap-1.5" accessibilityLiveRegion="polite">
              <Icon as={CircleAlert} size={16} className="text-destructive" />
              <Text className="shrink text-caption text-destructive">{fixedExpenseCardErrorMessage(assign.error)}</Text>
            </View>
          ) : null}
        </ScrollView>
      </BottomSheet>
    </>
  );
}

type CardOptionProps = {
  card: CardBilling;
  selected: boolean;
  disabled: boolean;
  onPress: () => void;
};

function CardOption({ card, selected, disabled, onPress }: CardOptionProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected, disabled }}
      disabled={disabled}
      onPress={onPress}
      className="h-touch flex-row items-center justify-between gap-3 active:opacity-70"
    >
      <Text className={cn("shrink text-body", selected ? "text-primary" : "text-popover-foreground")} numberOfLines={1}>
        {card.cardName}
      </Text>
      {selected ? <Icon as={Check} size={18} className="text-primary" /> : null}
    </Pressable>
  );
}

export { SubscriptionCardField };
