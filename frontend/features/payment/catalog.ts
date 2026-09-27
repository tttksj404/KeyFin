import { CalendarClock, CreditCard, House, Landmark, Repeat, Zap, type LucideIcon } from "lucide-react-native";

import { isManualExpenseType, type CalendarEntry, type ExpenseType, type ManualExpenseType } from "@/features/payment/model";

type ExpenseTypeOption<T extends ExpenseType> = { type: T; label: string; icon: LucideIcon };

/**
 * 고정지출 유형 5종(ExpenseType). 값은 계약(docs/api-contract.md 열거형)이고 라벨·아이콘·순서는 클라이언트 상수다.
 * UTILITY 는 달마다 금액이 달라 요청에 isVariable=true 가 붙는다 (FR-PAY-09).
 */
export const EXPENSE_TYPE_CATALOG: ExpenseTypeOption<ExpenseType>[] = [
  { type: "RENT", label: "월세·관리비", icon: House },
  { type: "SUBSCRIPTION", label: "구독", icon: Repeat },
  { type: "UTILITY", label: "공과금", icon: Zap },
  { type: "LOAN", label: "대출 상환", icon: Landmark },
  { type: "CARD_BILL", label: "카드 대금", icon: CreditCard },
];

/** 등록·수정 폼의 유형 칩. 카드 대금(CARD_BILL)은 청구서로 계산해 직접 등록할 수 없다(400 PAY_004) */
export const MANUAL_EXPENSE_TYPE_OPTIONS = EXPENSE_TYPE_CATALOG.filter(
  (option): option is ExpenseTypeOption<ManualExpenseType> => isManualExpenseType(option.type)
);

export function expenseTypeLabel(type: ExpenseType | null): string {
  return EXPENSE_TYPE_CATALOG.find((entry) => entry.type === type)?.label ?? "기타";
}

export function expenseTypeIcon(type: ExpenseType | null): LucideIcon {
  return EXPENSE_TYPE_CATALOG.find((entry) => entry.type === type)?.icon ?? CalendarClock;
}

/** 캘린더 항목 아이콘. 카드 청구는 카드, 나머지는 고정지출 유형 아이콘이다 */
export function calendarEntryIcon(entry: Pick<CalendarEntry, "type" | "expenseType">): LucideIcon {
  return entry.type === "CARD_BILL" ? CreditCard : expenseTypeIcon(entry.expenseType);
}
