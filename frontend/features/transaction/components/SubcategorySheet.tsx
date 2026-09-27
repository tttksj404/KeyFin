import { ChevronLeft, X } from "lucide-react-native";
import * as React from "react";
import { Pressable, ScrollView, View } from "react-native";

import { AmountInput } from "@/components/ui/amount-input";
import { Button } from "@/components/ui/button";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { ENVELOPE_CATALOG } from "@/features/budget/catalog";
import { USER_EXCLUDE_TAGS } from "@/features/transaction/catalog";
import { dutchAmountError, toDutchRequest, type ClassifyRequest, type Subcategory } from "@/features/transaction/model";
import { formatKRW, type KRW } from "@/lib/money";
import { cn } from "@/lib/utils";

// PAGE-20 거래 분류 시트 (Pencil 시안 없음 — DESIGN.md BottomSheet 규약: bg-popover · rounded-xl 상단 · 여백 20).
// 세분류 22종을 봉투 순서로 묶고, 아래에 제외 태그(더치페이·내 계좌 이동)를 둔다. subcategoryId 와 excludeTag 중 하나만 보낸다.
// 더치페이는 서버가 실제 부담액을 요구해(TRANSACTION_008) 같은 시트 안에서 금액 입력 단계로 넘어간다(사용자 결정 2026-09-15).
export const SHEET_TITLE = "카테고리 선택";
export const DUTCH_SHEET_TITLE = "더치페이 내 부담액";
export const SHEET_CLOSE_LABEL = "시트 닫기";
export const DUTCH_SUBMIT_LABEL = "더치페이로 저장";

type SubcategorySheetProps = {
  visible: boolean;
  subcategories: Subcategory[] | undefined;
  /** 현재 제안된 세분류. 선택 표시용 */
  selectedSubcategoryId: number | null;
  /** 분류할 거래의 금액. 더치페이 부담액 상한이다 */
  amount: KRW;
  disabled?: boolean;
  onSelect: (request: ClassifyRequest) => void;
  onClose: () => void;
};

type SheetStep = "pick" | "dutch";

function SubcategorySheet({ visible, subcategories, selectedSubcategoryId, amount, disabled = false, onSelect, onClose }: SubcategorySheetProps) {
  const [step, setStep] = React.useState<SheetStep>("pick");
  const [dutchDigits, setDutchDigits] = React.useState("");

  // 닫혔다 다시 열면 처음 단계부터. 부담액도 거래마다 새로 받는다.
  React.useEffect(() => {
    if (!visible) {
      setStep("pick");
      setDutchDigits("");
    }
  }, [visible]);

  const handleSelect = (request: ClassifyRequest) => {
    if ("excludeTag" in request && request.excludeTag === "DUTCH") {
      setStep("dutch");
      return;
    }
    onSelect(request);
  };

  return (
    <BottomSheet visible={visible} onClose={onClose} closeLabel={SHEET_CLOSE_LABEL}>
          <View className="flex-row items-center justify-between px-5 pt-5">
            <View className="flex-row items-center gap-2">
              {step === "dutch" ? (
                <Pressable accessibilityRole="button" accessibilityLabel="카테고리 선택으로" onPress={() => setStep("pick")} hitSlop={8}>
                  <Icon as={ChevronLeft} size={22} className="text-foreground" />
                </Pressable>
              ) : null}
              <Text className="text-h3 text-popover-foreground" accessibilityRole="header">
                {step === "dutch" ? DUTCH_SHEET_TITLE : SHEET_TITLE}
              </Text>
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel="닫기" onPress={onClose} hitSlop={8} className="h-touch w-touch items-center justify-center">
              <Icon as={X} size={20} className="text-card-foreground" />
            </Pressable>
          </View>
          {step === "dutch" ? (
            <DutchAmountStep
              amount={amount}
              digits={dutchDigits}
              disabled={disabled}
              onChange={setDutchDigits}
              onSubmit={() => onSelect(toDutchRequest(dutchDigits))}
            />
          ) : (
            <ScrollView className="max-h-96" contentContainerClassName="gap-4 px-5 pt-3">
              {subcategories ? (
                ENVELOPE_CATALOG.map((envelope) => (
                  <ChipGroup
                    key={envelope.id}
                    title={envelope.name}
                    chips={subcategories
                      .filter((subcategory) => subcategory.envelopeId === envelope.id)
                      .map((subcategory) => ({
                        key: `sub-${subcategory.id}`,
                        label: subcategory.name,
                        selected: subcategory.id === selectedSubcategoryId,
                        request: { subcategoryId: subcategory.id } as ClassifyRequest,
                      }))}
                    disabled={disabled}
                    onSelect={handleSelect}
                  />
                ))
              ) : (
                <View className="gap-3" accessibilityLabel="세분류 불러오는 중" accessible>
                  <Skeleton className="h-5 w-24" />
                  <Skeleton className="h-9 w-full rounded-lg" />
                  <Skeleton className="h-9 w-3/4 rounded-lg" />
                </View>
              )}
              <ChipGroup
                title="예산에서 제외"
                chips={USER_EXCLUDE_TAGS.map((tag) => ({
                  key: `tag-${tag.tag}`,
                  label: tag.label,
                  hint: tag.description,
                  selected: false,
                  // 더치페이는 부담액을 받은 뒤 보내므로 여기서는 단계 전환 신호로만 쓴다
                  request: (tag.tag === "DUTCH" ? { excludeTag: "DUTCH", adjustedAmount: 0 } : { excludeTag: tag.tag }) as ClassifyRequest,
                }))}
                disabled={disabled}
                onSelect={handleSelect}
              />
            </ScrollView>
          )}
    </BottomSheet>
  );
}

type DutchAmountStepProps = {
  amount: KRW;
  digits: string;
  disabled: boolean;
  onChange: (digits: string) => void;
  onSubmit: () => void;
};

// 결제 금액 중 내가 낸 만큼만 봉투에서 차감한다. 상한은 결제 금액이고 서버도 같은 규칙으로 다시 검사한다.
function DutchAmountStep({ amount, digits, disabled, onChange, onSubmit }: DutchAmountStepProps) {
  const error = dutchAmountError(digits, amount);
  const canSubmit = error === null && !disabled;

  return (
    <View className="gap-4 px-5 pt-3">
      <Text className="text-body-sm text-card-foreground">결제 금액 {formatKRW(amount)} 중 내가 낸 금액만 봉투에서 빼요.</Text>
      <AmountInput
        variant="field"
        className="h-input rounded-lg"
        value={digits}
        onChangeValue={onChange}
        max={amount}
        editable={!disabled}
        accessibilityLabel="내가 낸 금액"
        autoFocus
      />
      {digits === "" || error === null ? null : <Text className="text-caption text-destructive">{error}</Text>}
      <Button size="lg" className="h-button-lg rounded-lg" disabled={!canSubmit} accessibilityState={{ disabled: !canSubmit }} onPress={onSubmit}>
        <Text>{disabled ? "저장하는 중" : DUTCH_SUBMIT_LABEL}</Text>
      </Button>
    </View>
  );
}

type Chip = { key: string; label: string; hint?: string; selected: boolean; request: ClassifyRequest };

type ChipGroupProps = {
  title: string;
  chips: Chip[];
  disabled: boolean;
  onSelect: (request: ClassifyRequest) => void;
};

function ChipGroup({ title, chips, disabled, onSelect }: ChipGroupProps) {
  return (
    <View className="gap-2">
      <Text className="text-label text-card-foreground">{title}</Text>
      <View className="flex-row flex-wrap gap-2">
        {chips.map((chip) => (
          <Pressable
            key={chip.key}
            accessibilityRole="button"
            accessibilityLabel={chip.label}
            accessibilityHint={chip.hint}
            accessibilityState={{ selected: chip.selected, disabled }}
            disabled={disabled}
            onPress={() => onSelect(chip.request)}
            className={cn(
              "min-h-touch justify-center rounded-lg border px-4 active:opacity-70",
              chip.selected ? "border-primary bg-accent" : "border-border bg-card",
              disabled && "opacity-50"
            )}
          >
            <Text className={cn("text-label", chip.selected ? "text-primary" : "text-foreground")}>{chip.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

export { SubcategorySheet };
export type { SubcategorySheetProps };
