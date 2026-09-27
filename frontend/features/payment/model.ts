import { ContractMismatchError } from "@/lib/contract";
import { formatMonthDay, formatMonthKeyLabel, getKSTParts, KST_LOCAL_DATE_TIME, parseKSTDateKey } from "@/lib/date";
import { formatKRW, fromServerWon, toWon, type KRW } from "@/lib/money";

/**
 * GET /payments/calendar?month=YYYYMM 계약 (docs/api-contract.md PAYMENT, FR-PAY-01·02).
 * FIXED = 직접 등록한 고정지출(출금 계좌에서 나감) / CARD_SUBSCRIPTION = 금융망에서 동기화한 카드 정기결제(카드 대금에 포함돼
 * withdrawalAccountId 가 null) / CARD_BILL = 카드 청구(FR-PAY-02). 같은 날 순서는 서버가 정해 보내므로 다시 정렬하지 않는다.
 * prepared·shortage 는 서버 파생값이라 검증만 하고 다시 계산하지 않는다 — 출금 계좌 잔액 스냅샷을 같은 계좌의 오늘 이후 항목에
 * 날짜순으로 차감한 판정이고(FR-PAY-02, develop 69fdacb), 출금 계좌가 없거나(CARD_SUBSCRIPTION) 지난 항목은 null, 결제 완료 청구는 true/0 이다.
 * estimated=true 는 변동형 예상액이다(공과금, 이번 주 카드 승인 합계로 예상한 미발행 청구).
 */
export const PAYMENT_TYPES = ["FIXED", "CARD_SUBSCRIPTION", "CARD_BILL"] as const;
export type PaymentType = (typeof PAYMENT_TYPES)[number] | "UNKNOWN";

export type CalendarItemDto = {
  type: string;
  /** FIXED·CARD_SUBSCRIPTION 만 있다 */
  fixedExpenseId: number | null;
  /** CARD_BILL 만 있다 (백엔드 develop 69fdacb, FR-PAY-02) */
  cardId?: number | null;
  name: string;
  expenseType: string | null;
  amount: number;
  estimated: boolean;
  /** CARD_SUBSCRIPTION 은 카드 청구 경로라 null */
  withdrawalAccountId: number | null;
  /** FR-PAY-02 전까지 null */
  prepared: boolean | null;
  /** FR-PAY-02 전까지 null */
  shortage: number | null;
};

export type CalendarDayDto = {
  /** "2026-09-15", 말일 보정 적용 */
  date: string;
  items: CalendarItemDto[];
};

export type PaymentCalendarDto = {
  /** "YYYYMM" */
  month: string;
  days: CalendarDayDto[];
};

/** 결제 준비 상태. 서버가 아직 계산하지 않은 건(null)은 화면이 뱃지를 그리지 않는다 */
export type Preparation = { status: "PREPARED" } | { status: "SHORTAGE"; shortage: KRW };

export type CalendarEntry = {
  /** 같은 날 여러 건이 올 수 있어 date 만으로는 목록 키가 안 된다 */
  key: string;
  date: string;
  fixedExpenseId: number | null;
  /** 카드 청구(CARD_BILL)의 카드. 청구 상세(P1 GET /cards/{id}/billings)로 갈 때 쓴다 */
  cardId: number | null;
  withdrawalAccountId: number | null;
  /** 날짜의 일(1~31). 말일 보정된 값이라 고정지출의 출금일(paymentDay)과 다를 수 있다 */
  day: number;
  type: PaymentType;
  expenseType: ExpenseType | null;
  name: string;
  amount: KRW;
  estimated: boolean;
  preparation: Preparation | null;
};

export type PaymentCalendar = {
  entries: CalendarEntry[];
  /** 준비가 부족한 건수 */
  shortageCount: number;
  /** 준비 상태를 서버가 한 건이라도 계산했는지. false 면 '모두 준비됐어요' 같은 문구를 쓰지 않는다 */
  preparationKnown: boolean;
};

const DATE = /^\d{4}-(\d{2})-(\d{2})$/;

function won(value: unknown, field: string): KRW {
  try {
    return fromServerWon(value);
  } catch {
    throw new ContractMismatchError(field);
  }
}

function toType(raw: string): PaymentType {
  return (PAYMENT_TYPES as readonly string[]).includes(raw) ? (raw as PaymentType) : "UNKNOWN";
}

function toPreparation(item: CalendarItemDto): Preparation | null {
  if (item.prepared === null || item.prepared === undefined) return null;
  if (item.prepared) return { status: "PREPARED" };
  return { status: "SHORTAGE", shortage: won(item.shortage, "items.shortage") };
}

/* ───────────── 서버 계약: GET /cards/billings (docs/api-contract.md PAYMENT, 2026-09-16 대조) ───────────── */

/** 발행된 청구서 상태. 모르는 값은 UNKNOWN 으로 흡수한다 (규칙 80) */
export const BILLING_STATUSES = ["UNPAID", "PAID"] as const;
export type BillingStatus = (typeof BILLING_STATUSES)[number] | "UNKNOWN";

export type CardBillingStatementDto = {
  billingId: number;
  billingDate: string;
  amount: number;
  status: string;
  /** 출금 요일을 모르는 카드는 null */
  withdrawalDate: string | null;
  paidAt: string | null;
};

export type CardBillingDto = {
  cardId: number;
  cardName: string;
  /** 1(월)~7(일). 재연결이 필요한 카드는 null 이고 출금일도 없다 */
  withdrawalWeekday: number | null;
  withdrawalAccountId: number | null;
  estimated: { amount: number; approvalCount: number; withdrawalDate: string | null };
  /** 아직 청구서가 없으면 null */
  latestStatement: CardBillingStatementDto | null;
};

export type CardBillingsDto = {
  asOf: string;
  cycleFrom: string;
  nextBillingDate: string;
  cards: CardBillingDto[];
};

export type CardBillingStatement = {
  billingId: number;
  billingDate: string;
  amount: KRW;
  status: BillingStatus;
  withdrawalDate: string | null;
  paidAt: string | null;
};

export type CardBilling = {
  cardId: number;
  cardName: string;
  /** 이번 주기(cycleFrom~asOf) 승인 합계. 확정 전 예상값이다 */
  estimatedAmount: KRW;
  approvalCount: number;
  /** 예상 출금일. 출금 요일을 모르는 카드는 null */
  estimatedWithdrawalDate: string | null;
  /** 발행된 최근 청구서 1건 */
  statement: CardBillingStatement | null;
};

export type CardBillings = {
  asOf: string;
  cycleFrom: string;
  nextBillingDate: string;
  cards: CardBilling[];
};

export function toCardBillings(dto: CardBillingsDto): CardBillings {
  return {
    asOf: dto.asOf,
    cycleFrom: dto.cycleFrom,
    nextBillingDate: dto.nextBillingDate,
    cards: dto.cards.map((card) => ({
      cardId: card.cardId,
      cardName: card.cardName,
      estimatedAmount: won(card.estimated.amount, "estimated.amount"),
      approvalCount: card.estimated.approvalCount,
      estimatedWithdrawalDate: card.estimated.withdrawalDate,
      statement: card.latestStatement === null ? null : toStatement(card.latestStatement, "latestStatement"),
    })),
  };
}

function toStatement(dto: CardBillingStatementDto, field: string): CardBillingStatement {
  return {
    billingId: dto.billingId,
    billingDate: dto.billingDate,
    amount: won(dto.amount, `${field}.amount`),
    status: pickStatus(dto.status),
    withdrawalDate: dto.withdrawalDate,
    paidAt: dto.paidAt,
  };
}

function pickStatus(raw: string): BillingStatus {
  return (BILLING_STATUSES as readonly string[]).includes(raw) ? (raw as BillingStatus) : "UNKNOWN";
}

/** 카드 한 장의 청구 요약. 아직 동기화 전이면 null 이라 화면이 금액 줄을 생략한다 */
export function findCardBilling(billings: CardBillings | undefined, cardId: number): CardBilling | null {
  return billings?.cards.find((card) => card.cardId === cardId) ?? null;
}

/* ───────────── 서버 계약: GET /cards/{cardId}/billings (백엔드 develop CardBillingController, 2026-09-17 대조) ───────────── */

/** 이번 주기 예정액의 근거가 된 승인 한 건. 최신순이고 취소 거래는 서버가 뺀다. merchantName 은 거래 원문이다 */
export type CardBillingApprovalDto = {
  transactionId: number;
  date: string;
  merchantName: string;
  amount: number;
};

export type CardBillingDetailDto = {
  asOf: string;
  cycleFrom: string;
  /** 이번 주기 승인이 청구서로 발행되는 다음 월요일 */
  nextBillingDate: string;
  cardId: number;
  cardName: string;
  withdrawalWeekday: number | null;
  withdrawalAccountId: number | null;
  estimated: { amount: number; withdrawalDate: string | null; approvals: CardBillingApprovalDto[] };
  /** 청구서 발행 월 범위 "YYYYMM". 요청에서 생략하면 전월~이번 달 */
  from: string;
  to: string;
  /** 발행된 청구서, 최신순 */
  statements: CardBillingStatementDto[];
};

export type CardBillingApproval = {
  transactionId: number;
  date: string;
  merchantName: string;
  amount: KRW;
};

export type CardBillingDetail = {
  cardId: number;
  cardName: string;
  asOf: string;
  cycleFrom: string;
  nextBillingDate: string;
  /** 이번 주기 승인 합계. 청구서로 발행되기 전의 예상값이다 */
  estimatedAmount: KRW;
  /** 출금 요일을 모르는 카드(재연결 필요)는 null */
  estimatedWithdrawalDate: string | null;
  approvals: CardBillingApproval[];
  fromMonth: string;
  toMonth: string;
  statements: CardBillingStatement[];
};

function dateKey(value: unknown, field: string): string {
  if (typeof value !== "string" || !DATE.test(value)) throw new ContractMismatchError(field);
  return value;
}

function optionalDateKey(value: unknown, field: string): string | null {
  return value === null || value === undefined ? null : dateKey(value, field);
}

/** 상세 화면은 날짜를 모두 읽어 그리므로 요약(toCardBillings)과 달리 형식까지 검사한다 */
function toDetailStatement(dto: CardBillingStatementDto): CardBillingStatement {
  if (dto.paidAt !== null && dto.paidAt !== undefined && !KST_LOCAL_DATE_TIME.test(dto.paidAt)) {
    throw new ContractMismatchError("statements.paidAt");
  }
  return {
    ...toStatement(dto, "statements"),
    billingDate: dateKey(dto.billingDate, "statements.billingDate"),
    withdrawalDate: optionalDateKey(dto.withdrawalDate, "statements.withdrawalDate"),
    paidAt: dto.paidAt ?? null,
  };
}

export function toCardBillingDetail(dto: CardBillingDetailDto): CardBillingDetail {
  if (!MONTH_KEY.test(dto.from)) throw new ContractMismatchError("from");
  if (!MONTH_KEY.test(dto.to)) throw new ContractMismatchError("to");
  return {
    cardId: dto.cardId,
    cardName: dto.cardName,
    asOf: dateKey(dto.asOf, "asOf"),
    cycleFrom: dateKey(dto.cycleFrom, "cycleFrom"),
    nextBillingDate: dateKey(dto.nextBillingDate, "nextBillingDate"),
    estimatedAmount: won(dto.estimated.amount, "estimated.amount"),
    estimatedWithdrawalDate: optionalDateKey(dto.estimated.withdrawalDate, "estimated.withdrawalDate"),
    approvals: dto.estimated.approvals.map((approval) => ({
      transactionId: approval.transactionId,
      date: dateKey(approval.date, "approvals.date"),
      merchantName: approval.merchantName,
      amount: won(approval.amount, "approvals.amount"),
    })),
    fromMonth: dto.from,
    toMonth: dto.to,
    statements: dto.statements.map(toDetailStatement),
  };
}

/** "2026-09-14" → "9월 14일". 한 줄에 날짜가 여럿 들어가 요일은 붙이지 않는다 (Pencil PAGE-33 LsAZT) */
export function billingDateLabel(key: string): string {
  const { month, day } = getKSTParts(parseKSTDateKey(key));
  return `${month}월 ${day}일`;
}

/** 예정액 아래 한 줄: "9월 14일 ~ 9월 16일 승인 4건 · 9월 23일 출금 예정". 주기 첫날(월요일)이면 날짜 하나만 쓴다 */
export function cardBillingCycleCaption(detail: CardBillingDetail): string {
  const period =
    detail.cycleFrom === detail.asOf
      ? billingDateLabel(detail.asOf)
      : `${billingDateLabel(detail.cycleFrom)} ~ ${billingDateLabel(detail.asOf)}`;
  const withdrawal =
    detail.estimatedWithdrawalDate === null ? "출금일 확인 필요" : `${billingDateLabel(detail.estimatedWithdrawalDate)} 출금 예정`;
  return `${period} 승인 ${detail.approvals.length}건 · ${withdrawal}`;
}

export type CardBillingNotice = { tone: "info" | "warning"; message: string };

/** 예정액이 확정값이 아니라는 안내. 출금 요일을 모르는 카드는 출금일을 계산할 수 없다는 경고로 바꾼다 */
export function cardBillingNotice(detail: CardBillingDetail): CardBillingNotice {
  if (detail.estimatedWithdrawalDate === null) {
    return {
      tone: "warning",
      message: "카드사에서 출금 요일을 받지 못해 출금일을 계산할 수 없어요. 청구서가 발행되면 금액은 그대로 보여요.",
    };
  }
  return {
    tone: "info",
    message: `${formatMonthDay(parseKSTDateKey(detail.nextBillingDate))}에 청구서로 확정돼요. 그 전까지는 승인이 더해지면 금액이 바뀌어요.`,
  };
}

/** "8월 ~ 9월에 발행된 청구서예요." 같은 달이면 한 달만 쓴다 */
export function statementRangeLabel(detail: CardBillingDetail): string {
  const to = formatMonthKeyLabel(detail.toMonth);
  return detail.fromMonth === detail.toMonth
    ? `${to}에 발행된 청구서예요.`
    : `${formatMonthKeyLabel(detail.fromMonth)} ~ ${to}에 발행된 청구서예요.`;
}

const BILLING_STATUS_LABELS: Record<BillingStatus, string> = {
  UNPAID: "미결제",
  PAID: "결제 완료",
  UNKNOWN: "확인 중",
};

export function billingStatusLabel(status: BillingStatus): string {
  return BILLING_STATUS_LABELS[status];
}

export function statementTitle(statement: CardBillingStatement): string {
  return `${billingDateLabel(statement.billingDate)} 발행`;
}

/**
 * 청구서 행의 아랫줄. 결제 완료는 결제일, 그 밖에는 출금일을 쓴다.
 * 동기화(08:00·17:00)가 출금(16:00)보다 늦어 출금일이 지났는데 UNPAID 일 수 있어, 지난 날짜는 '예정' 이라 부르지 않는다.
 */
export function statementCaption(statement: CardBillingStatement, todayKey: string): string {
  if (statement.status === "PAID") {
    if (statement.paidAt !== null) return `${billingDateLabel(statement.paidAt.slice(0, 10))} 결제`;
    if (statement.withdrawalDate !== null) return `${billingDateLabel(statement.withdrawalDate)} 결제`;
    return "결제 완료";
  }
  if (statement.withdrawalDate === null) return "출금일 확인 필요";
  const date = billingDateLabel(statement.withdrawalDate);
  return statement.withdrawalDate >= todayKey ? `${date} 출금 예정` : `${date} 출금 확인 중`;
}

/** 카드 청구 상세 라우트(`/payment/card-billing/[id]`)의 카드 id. 양의 정수가 아니면 null (규칙 50: 파라미터는 믿지 않는다) */
export function parseCardId(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw !== undefined && /^[1-9]\d*$/.test(raw) ? Number(raw) : null;
}

export function toPaymentCalendar(dto: PaymentCalendarDto): PaymentCalendar {
  const days = [...dto.days].sort((a, b) => a.date.localeCompare(b.date));
  const entries = days.flatMap((day) => {
    const matched = DATE.exec(day.date);
    if (!matched) throw new ContractMismatchError("days.date");
    return day.items.map(
      (item, index): CalendarEntry => ({
        key: `${day.date}#${index}`,
        date: day.date,
        fixedExpenseId: item.fixedExpenseId ?? null,
        cardId: item.cardId ?? null,
        withdrawalAccountId: item.withdrawalAccountId ?? null,
        day: Number(matched[2]),
        type: toType(item.type),
        expenseType: toExpenseType(item.expenseType),
        name: item.name,
        amount: won(item.amount, "items.amount"),
        estimated: item.estimated ?? false,
        preparation: toPreparation(item),
      })
    );
  });

  return {
    entries,
    shortageCount: entries.filter((entry) => entry.preparation?.status === "SHORTAGE").length,
    preparationKnown: entries.some((entry) => entry.preparation !== null),
  };
}

export const PREPARED_LABEL = "준비됨";

/** 뱃지·접근성 문구. 준비 상태를 모르면 null 이라 뱃지를 그리지 않는다 */
export function preparationLabel(preparation: Preparation | null): string | null {
  if (preparation === null) return null;
  return preparation.status === "PREPARED" ? PREPARED_LABEL : `부족 ${formatKRW(preparation.shortage)}`;
}

/** 고칠 수 있는 건 직접 등록한 고정지출뿐이다. 동기화된 카드 정기결제는 서버가 409(PAY_002)로 막는다 */
export function isEditableEntry(entry: CalendarEntry): entry is CalendarEntry & { fixedExpenseId: number } {
  return entry.type === "FIXED" && entry.fixedExpenseId !== null;
}

/**
 * 캘린더 항목을 눌러 고정지출 화면으로 갈 수 있는지. 고정지출 행이 있는 항목은 모두 연다 — 직접 등록한 것은 수정 폼,
 * 동기화된 카드 정기결제는 읽기 전용 상세다(사용자 결정 2026-09-15: 한 항목만 눌리지 않으면 목록의 통일감이 깨진다).
 * 카드 청구(CARD_BILL)는 고정지출 행이 없어 여기가 아니라 canOpenCardBilling 으로 카드 청구 상세(PAGE-33)를 연다.
 */
export function canOpenEntry(entry: CalendarEntry): entry is CalendarEntry & { fixedExpenseId: number } {
  return entry.fixedExpenseId !== null && (entry.type === "FIXED" || entry.type === "CARD_SUBSCRIPTION");
}

/** 캘린더의 카드 청구 항목을 눌러 카드 청구 상세(PAGE-33, GET /cards/{id}/billings)로 갈 수 있는지. cardId 가 없으면 열 곳이 없다 */
export function canOpenCardBilling(entry: CalendarEntry): entry is CalendarEntry & { cardId: number } {
  return entry.type === "CARD_BILL" && entry.cardId !== null;
}

/** 자산 탭 "이번 달 정기결제 예정": 오늘 포함 이후 건을 날짜순으로 limit 건까지 */
export function upcomingEntries(calendar: PaymentCalendar, todayKey: string, limit: number): CalendarEntry[] {
  return calendar.entries.filter((entry) => entry.date >= todayKey).slice(0, limit);
}

/** 방 캘린더 에셋에 한 건만 띄우기 위한 선택. 오늘 이후 첫 건, 이번 달이 다 지났으면 마지막 건. */
export function upcomingEntry(calendar: PaymentCalendar, todayKey: string): CalendarEntry | null {
  if (calendar.entries.length === 0) return null;
  return calendar.entries.find((entry) => entry.date >= todayKey) ?? calendar.entries[calendar.entries.length - 1];
}

/** 고정지출 유형 (docs/api-contract.md 열거형 ExpenseType) */
export const EXPENSE_TYPES = ["RENT", "SUBSCRIPTION", "UTILITY", "LOAN", "CARD_BILL"] as const;
export type ExpenseType = (typeof EXPENSE_TYPES)[number];

/** 사용자가 직접 등록할 수 있는 유형. CARD_BILL 은 청구서로 엔진이 계산해 등록하면 400(PAY_004)이다 */
export const MANUAL_EXPENSE_TYPES = ["RENT", "SUBSCRIPTION", "UTILITY", "LOAN"] as const;
export type ManualExpenseType = (typeof MANUAL_EXPENSE_TYPES)[number];

function toExpenseType(raw: string | null | undefined): ExpenseType | null {
  return raw !== null && raw !== undefined && (EXPENSE_TYPES as readonly string[]).includes(raw) ? (raw as ExpenseType) : null;
}

export function isManualExpenseType(type: ExpenseType | null): type is ManualExpenseType {
  return type !== null && (MANUAL_EXPENSE_TYPES as readonly string[]).includes(type);
}

/**
 * GET /fixed-expenses 계약 (FR-PAY-07). 활성 고정지출을 등록 순으로 준다. 금융망 정기결제에서 동기화한 항목도 섞여 오며
 * synced=true 는 수정·삭제가 409(PAY_002)라 화면이 잠근다. 동기화 항목은 출금 계좌가 없어(카드 청구 경로) withdrawalAccountId 가 null 이다.
 */
export type FixedExpenseDto = {
  id: number;
  name: string;
  expenseType: string;
  /** 자동 감지 CARD_BILL 은 null(엔진 계산) */
  amount: number | null;
  isVariable: boolean;
  /** 1~31, 말일 보정 전 저장값 */
  paymentDay: number;
  withdrawalAccountId: number | null;
  synced: boolean;
  /** 동기화 항목의 결제 카드(-183, 2026-09-24). 미지정·수동 항목은 null, 필드 추가 전 서버는 보내지 않는다 */
  cardId?: number | null;
};

export type FixedExpenseListDto = FixedExpenseDto[];

export type FixedExpense = {
  id: number;
  name: string;
  /** 계약에 없는 값이면 null */
  expenseType: ExpenseType | null;
  amount: KRW | null;
  isVariable: boolean;
  paymentDay: number;
  withdrawalAccountId: number | null;
  synced: boolean;
  cardId: number | null;
};

export const MIN_PAYMENT_DAY = 1;
export const MAX_PAYMENT_DAY = 31;
export const MAX_FIXED_EXPENSE_NAME_LENGTH = 50;

export function toFixedExpense(dto: FixedExpenseDto): FixedExpense {
  if (!Number.isInteger(dto.paymentDay) || dto.paymentDay < MIN_PAYMENT_DAY || dto.paymentDay > MAX_PAYMENT_DAY) {
    throw new ContractMismatchError("paymentDay");
  }
  return {
    id: dto.id,
    name: dto.name,
    expenseType: toExpenseType(dto.expenseType),
    amount: dto.amount === null || dto.amount === undefined ? null : won(dto.amount, "amount"),
    isVariable: dto.isVariable,
    paymentDay: dto.paymentDay,
    withdrawalAccountId: dto.withdrawalAccountId ?? null,
    synced: dto.synced,
    cardId: dto.cardId ?? null,
  };
}

export function toFixedExpenses(dto: FixedExpenseListDto): FixedExpense[] {
  return dto.map(toFixedExpense);
}

export function findFixedExpense(expenses: FixedExpense[], id: number): FixedExpense | null {
  return expenses.find((expense) => expense.id === id) ?? null;
}

/** 고정지출 관리 화면: 직접 등록한 항목(고칠 수 있음)과 동기화된 카드 정기결제(잠김)를 나눈다. 순서는 서버의 등록 순 그대로다 */
export function splitFixedExpenses(expenses: FixedExpense[]): { manual: FixedExpense[]; synced: FixedExpense[] } {
  return {
    manual: expenses.filter((expense) => !expense.synced),
    synced: expenses.filter((expense) => expense.synced),
  };
}

const MONTH_END_ADJUSTED_FROM = 29;

/** "매달 15일", 29~31일은 없는 달에 말일로 나간다는 뜻을 붙인다(보정은 서버) */
export function paymentDayLabel(paymentDay: number): string {
  return paymentDay >= MONTH_END_ADJUSTED_FROM ? `매달 ${paymentDay}일 (없는 달은 말일)` : `매달 ${paymentDay}일`;
}

/** 고정지출 등록·수정 화면(PAGE-26)의 입력값. 금액·출금일은 입력 중 상태를 그대로 두려고 문자열이다 */
export type FixedExpenseForm = {
  name: string;
  expenseType: ManualExpenseType;
  /** 원 단위 숫자만 있는 문자열(AmountInput) */
  amount: string;
  /** "1"~"31" */
  paymentDay: string;
  withdrawalAccountId: number | null;
};

/** POST /fixed-expenses 와 PUT /fixed-expenses/{id} 요청. PUT 은 이 본문 전체로 교체한다 (FR-PAY-07) */
export type FixedExpenseRequest = {
  name: string;
  expenseType: ManualExpenseType;
  /** 원, 1 이상. 변동형은 예상액 */
  amount: number;
  isVariable: boolean;
  paymentDay: number;
  withdrawalAccountId: number;
};

export type FixedExpenseResponseDto = { id: number };

const DEFAULT_EXPENSE_TYPE: ManualExpenseType = "SUBSCRIPTION";

export const EMPTY_FIXED_EXPENSE_FORM: FixedExpenseForm = {
  name: "",
  expenseType: DEFAULT_EXPENSE_TYPE,
  amount: "",
  paymentDay: "",
  withdrawalAccountId: null,
};

/**
 * 수정 폼 초기값. 출금일은 말일 보정 전 저장값(paymentDay)이라 그대로 저장해도 날짜가 바뀌지 않는다.
 * 직접 등록할 수 없는 유형(CARD_BILL·모르는 값)은 기본 유형에서 다시 고르게 한다.
 */
export function toFixedExpenseForm(expense: FixedExpense): FixedExpenseForm {
  return {
    name: expense.name,
    expenseType: isManualExpenseType(expense.expenseType) ? expense.expenseType : DEFAULT_EXPENSE_TYPE,
    amount: expense.amount === null ? "" : String(toWon(expense.amount)),
    paymentDay: String(expense.paymentDay),
    withdrawalAccountId: expense.withdrawalAccountId,
  };
}

const PAYMENT_DAY = /^\d{1,2}$/;

/**
 * 저장할 수 없는 이유. 없으면 null.
 * 서버가 다시 검사하므로(출금일 29~31 말일 보정도 서버) 여기서는 보낼 수 있는 형태인지만 본다.
 */
export function fixedExpenseFormError(form: FixedExpenseForm): string | null {
  const name = form.name.trim();
  if (name === "") return "이름을 입력해 주세요.";
  if (name.length > MAX_FIXED_EXPENSE_NAME_LENGTH) return `이름은 ${MAX_FIXED_EXPENSE_NAME_LENGTH}자까지 쓸 수 있어요.`;
  if (form.amount === "" || toWon(form.amount) <= 0n) return "금액을 입력해 주세요.";
  const day = Number(form.paymentDay);
  if (!PAYMENT_DAY.test(form.paymentDay) || day < MIN_PAYMENT_DAY || day > MAX_PAYMENT_DAY) {
    return `출금일은 ${MIN_PAYMENT_DAY}~${MAX_PAYMENT_DAY} 사이로 입력해 주세요.`;
  }
  if (form.withdrawalAccountId === null) return "출금 계좌를 골라 주세요.";
  return null;
}

/** 공과금은 달마다 금액이 달라 변동형(예상액)으로 보낸다 (FR-PAY-09). 나머지 유형은 고정 금액이다 */
export function isVariableExpenseType(type: ManualExpenseType): boolean {
  return type === "UTILITY";
}

/** 화면 값 → 요청 본문. PUT 이 전체 교체라 isVariable 도 항상 명시한다 */
export function toFixedExpenseRequest(form: FixedExpenseForm): FixedExpenseRequest {
  const error = fixedExpenseFormError(form);
  if (error !== null || form.withdrawalAccountId === null) throw new Error(error ?? "고정지출 입력이 올바르지 않습니다");
  return {
    name: form.name.trim(),
    expenseType: form.expenseType,
    amount: Number(toWon(form.amount)),
    isVariable: isVariableExpenseType(form.expenseType),
    paymentDay: Number(form.paymentDay),
    withdrawalAccountId: form.withdrawalAccountId,
  };
}

export type CalendarDayGroup = {
  date: string;
  day: number;
  entries: CalendarEntry[];
};

/** 결제 캘린더(PAGE-24)는 날짜로 묶어 보여준다. entries 는 이미 날짜순이다 */
export function groupEntriesByDate(entries: CalendarEntry[]): CalendarDayGroup[] {
  const groups: CalendarDayGroup[] = [];
  for (const entry of entries) {
    const last = groups[groups.length - 1];
    if (last !== undefined && last.date === entry.date) last.entries.push(entry);
    else groups.push({ date: entry.date, day: entry.day, entries: [entry] });
  }
  return groups;
}

export const NEW_FIXED_EXPENSE_ID = "new";

/** 고정지출 화면의 라우트 파라미터. "new" 는 등록, 양의 정수는 수정, 나머지는 잘못된 주소다 */
export type FixedExpenseRoute = { mode: "create" } | { mode: "edit"; id: number } | null;

export function parseFixedExpenseRoute(value: string | string[] | undefined): FixedExpenseRoute {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === NEW_FIXED_EXPENSE_ID) return { mode: "create" };
  return raw !== undefined && /^[1-9]\d*$/.test(raw) ? { mode: "edit", id: Number(raw) } : null;
}

const MONTH_KEY = /^\d{4}(0[1-9]|1[0-2])$/;

/** 결제 캘린더의 month 검색 파라미터. 형식이 틀리면 이번 달. 앞으로 나갈 출금이라 미래 달도 본다 */
export function parseCalendarMonth(value: string | string[] | undefined, currentMonth: string): string {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw !== undefined && MONTH_KEY.test(raw) ? raw : currentMonth;
}

/**
 * GET /transfers 계약 (노션 "이체 제안·이력 조회" = 백엔드 feature/41-approval-transfer(f75c20a) 코드, 2026-09-16 대조).
 * **`data` 가 배열이다** — items 래퍼가 없다. 쿼리는 status 하나뿐이고 month 필터는 없다.
 * 상태는 PROPOSED → APPROVED → EXECUTED / FAILED / CANCELED 이고 모르는 값은 UNKNOWN 으로 흡수한다 (규칙 80).
 * 제안은 08:30 배치가 만든다: 출금일이 오늘·내일이고 부족액이 있는 항목마다 1건(수입 계좌 → 출금 계좌).
 */
export const TRANSFER_STATUSES = ["PROPOSED", "APPROVED", "EXECUTED", "FAILED", "CANCELED"] as const;
export type TransferStatus = (typeof TRANSFER_STATUSES)[number] | "UNKNOWN";

/** 제안이 대신 내주는 출금 건. 캘린더 항목 유형과 같은 값이다 */
export const TRANSFER_PURPOSE_TYPES = ["FIXED", "CARD_BILL"] as const;
export type TransferPurposeType = (typeof TRANSFER_PURPOSE_TYPES)[number] | "UNKNOWN";

export type TransferDto = {
  id: number;
  status: string;
  /** "2026-09-14" 실행 예정일(= 제안한 날) */
  scheduledDate: string;
  /** "2026-09-15" 대상 출금일. 고정지출·화~일 출금 카드는 하루 뒤, 월요일 출금 카드는 같은 날 */
  dueDate: string;
  requiredAmount: number;
  fromAccountId: number;
  toAccountId: number;
  purpose: {
    type: string;
    /** FIXED 만 */
    fixedExpenseId: number | null;
    /** CARD_BILL 만 */
    cardBillingId: number | null;
    name: string;
  };
  /** EXECUTED 만 "2026-09-14T09:12:00" */
  executedAt?: string | null;
  /** FAILED 는 금융망 코드+사유, CANCELED 는 출금일 경과·부족액 해소 */
  failReason?: string | null;
  /** "2026-09-14T08:30:12" */
  createdAt: string;
};

/** 목록 응답 — 커서 페이지(-62, 2026-09-16). 커서는 마지막 항목 id, 마지막 쪽은 null */
export type TransferListDto = { items: TransferDto[]; nextCursor: number | null };

/** 감사 로그 한 줄의 종류. EXECUTE 실행 · HOLD 보류(안전장치·나중에) · FAIL 금융망 거부 · CANCEL 배치 정리 */
export const TRANSFER_HISTORY_ACTIONS = ["EXECUTE", "HOLD", "FAIL", "CANCEL"] as const;
export type TransferHistoryAction = (typeof TRANSFER_HISTORY_ACTIONS)[number] | "UNKNOWN";

/** GET /transfers/{id} — 제안 한 건 + 감사 타임라인(오래된 순) */
export type TransferDetailDto = {
  transfer: TransferDto;
  history: { action: string; basis: string; at: string }[];
};

export type Transfer = {
  id: number;
  status: TransferStatus;
  scheduledDate: string;
  /** 화면에 "언제 나갈 돈인지" 로 쓰는 날짜는 이쪽이다 */
  dueDate: string;
  requiredAmount: KRW;
  fromAccountId: number;
  toAccountId: number;
  executedAt: string | null;
  failReason: string | null;
  createdAt: string;
  purposeName: string;
  purposeType: TransferPurposeType;
  purposeFixedExpenseId: number | null;
  purposeCardBillingId: number | null;
};

export type ApproveTransferDto = { id: number; status: string; executedAt?: string | null; failReason?: string | null };

const TRANSFER_DATE = /^\d{4}-\d{2}-\d{2}$/;

function toTransferStatus(raw: string): TransferStatus {
  return (TRANSFER_STATUSES as readonly string[]).includes(raw) ? (raw as TransferStatus) : "UNKNOWN";
}

function toTransferPurposeType(raw: string): TransferPurposeType {
  return (TRANSFER_PURPOSE_TYPES as readonly string[]).includes(raw) ? (raw as TransferPurposeType) : "UNKNOWN";
}

export function toTransfer(dto: TransferDto): Transfer {
  if (!TRANSFER_DATE.test(dto.scheduledDate)) throw new ContractMismatchError("scheduledDate");
  if (!TRANSFER_DATE.test(dto.dueDate)) throw new ContractMismatchError("dueDate");
  return {
    id: dto.id,
    status: toTransferStatus(dto.status),
    scheduledDate: dto.scheduledDate,
    dueDate: dto.dueDate,
    requiredAmount: won(dto.requiredAmount, "requiredAmount"),
    fromAccountId: dto.fromAccountId,
    toAccountId: dto.toAccountId,
    executedAt: dto.executedAt ?? null,
    failReason: dto.failReason ?? null,
    createdAt: dto.createdAt,
    purposeName: dto.purpose.name,
    purposeType: toTransferPurposeType(dto.purpose.type),
    purposeFixedExpenseId: dto.purpose.fixedExpenseId ?? null,
    purposeCardBillingId: dto.purpose.cardBillingId ?? null,
  };
}

export function toTransfers(dtos: TransferDto[]): Transfer[] {
  return dtos.map(toTransfer);
}

export type TransferPage = { items: Transfer[]; nextCursor: number | null };

export function toTransferPage(dto: TransferListDto): TransferPage {
  return { items: toTransfers(dto.items), nextCursor: dto.nextCursor };
}

export type TransferHistoryEntry = { action: TransferHistoryAction; basis: string; at: string };
export type TransferDetail = { transfer: Transfer; history: TransferHistoryEntry[] };

function toHistoryAction(raw: string): TransferHistoryAction {
  return (TRANSFER_HISTORY_ACTIONS as readonly string[]).includes(raw) ? (raw as TransferHistoryAction) : "UNKNOWN";
}

/** 승인 화면(PAGE-25)이 쓰는 단건 조회. 목록 첫 쪽에 없는 제안(딥링크·푸시)도 이걸로 연다 */
export function toTransferDetail(dto: TransferDetailDto): TransferDetail {
  return {
    transfer: toTransfer(dto.transfer),
    history: dto.history.map((entry) => ({ action: toHistoryAction(entry.action), basis: entry.basis, at: entry.at })),
  };
}

export function findTransfer(transfers: Transfer[], id: number): Transfer | null {
  return transfers.find((transfer) => transfer.id === id) ?? null;
}

/**
 * 캘린더 부족 항목에 대응하는 승인 가능한 이체 제안. 푸시(P1) 전까지 이체 승인(PAGE-25)으로 가는 유일한 앱 내 진입점이다(사용자 결정 2026-09-16).
 * 제안은 08:30 배치가 출금일이 오늘·내일인 건에만 만들어서, 부족이어도 아직 제안이 없으면 null 이다 — 그때는 뱃지만 있고 눌리지 않는다.
 * FIXED 는 fixedExpenseId + dueDate 로 정확히 잇는다. CARD_BILL 은 캘린더가 cardBillingId 를 주지 않아 dueDate + 출금 계좌 + 카드명으로 잇는다 (TBD: 캘린더 응답에 cardBillingId 요청).
 */
export function findTransferForEntry(transfers: Transfer[], entry: CalendarEntry): Transfer | null {
  if (entry.preparation?.status !== "SHORTAGE") return null;
  const match = transfers.find((transfer) => {
    if (!canApproveTransfer(transfer) || transfer.dueDate !== entry.date) return false;
    if (entry.type === "FIXED") return transfer.purposeType === "FIXED" && transfer.purposeFixedExpenseId === entry.fixedExpenseId;
    if (entry.type === "CARD_BILL") {
      return transfer.purposeType === "CARD_BILL" && transfer.toAccountId === entry.withdrawalAccountId && transfer.purposeName === entry.name;
    }
    return false;
  });
  return match ?? null;
}

/**
 * 승인을 보낼 수 있는 상태. PROPOSED 는 안전장치 4검사를 거쳐 새로 실행하고,
 * APPROVED 는 금융망 응답이 유실된 건이라 **같은 기관거래고유번호로 재시도**한다(서버가 검사를 건너뛴다).
 * 이미 성공했던 이체면 금융망이 중복(H1007)으로 답해 EXECUTED 가 되므로 이중 이체가 되지 않는다.
 */
export function canApproveTransfer(transfer: Transfer): boolean {
  return transfer.status === "PROPOSED" || transfer.status === "APPROVED";
}

/** 연기는 승인 대기(PROPOSED)만 받는다. 실행 중(APPROVED)에 보내면 409 PAY_006 이다 */
export function canPostponeTransfer(transfer: Transfer): boolean {
  return transfer.status === "PROPOSED";
}

const TRANSFER_STATUS_LABELS: Record<TransferStatus, string> = {
  PROPOSED: "승인 대기",
  APPROVED: "처리 중",
  EXECUTED: "이체 완료",
  FAILED: "이체 실패",
  CANCELED: "취소됨",
  UNKNOWN: "확인 중",
};

export function transferStatusLabel(status: TransferStatus): string {
  return TRANSFER_STATUS_LABELS[status];
}

const TRANSFER_HISTORY_LABELS: Record<TransferHistoryAction, string> = {
  EXECUTE: "이체 완료",
  HOLD: "보류",
  FAIL: "이체 실패",
  CANCEL: "취소",
  UNKNOWN: "기록",
};

/** 감사 타임라인 한 줄의 제목. 종류만 우리말로 적고 서버 근거 문구(basis)는 고치지 않는다 (규칙 80) */
export function transferHistoryLabel(action: TransferHistoryAction): string {
  return TRANSFER_HISTORY_LABELS[action];
}

/** 이체 승인 라우트(`/payment/transfer/[id]`)의 id. 양의 정수가 아니면 null — 푸시·딥링크 값은 믿지 않는다 (규칙 80) */
export function parseTransferId(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw !== undefined && /^[1-9]\d*$/.test(raw) ? Number(raw) : null;
}
