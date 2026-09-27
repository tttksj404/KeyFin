import { ContractMismatchError } from "@/lib/contract";
import { formatDate, formatDateTime, KST_LOCAL_DATE_TIME, parseKSTDateKey, parseKSTLocalDateTime } from "@/lib/date";
import { compareKRW, formatKRW, fromServerWon, toWon, type KRW } from "@/lib/money";

/**
 * TRANSACTION 계약 (docs/api-contract.md TRANSACTION). 열거형은 ERD 값이며 모르는 값은 UNKNOWN 으로 흡수한다.
 */
export const TX_TYPES = ["CARD", "DEPOSIT", "WITHDRAW", "TRANSFER", "CARD_BILL"] as const;
export const CONFIRM_STATUSES = ["AUTO", "PENDING", "CONFIRMED"] as const;
/** RESTORE 는 환급 입금을 봉투로 되돌리는 태그(develop 2026-09-15, 입금 + subcategoryId 와 함께) — 화면 입력은 아직 없다 (TBD) */
export const EXCLUDE_TAGS = ["NONE", "DUTCH", "SELF_TRANSFER", "EMERGENCY", "CARRYOVER", "RESTORE"] as const;
export const TX_STATUSES = ["NORMAL", "CANCELED"] as const;

export type TxType = (typeof TX_TYPES)[number] | "UNKNOWN";
export type ConfirmStatus = (typeof CONFIRM_STATUSES)[number] | "UNKNOWN";
export type ExcludeTag = (typeof EXCLUDE_TAGS)[number] | "UNKNOWN";
export type TxStatus = (typeof TX_STATUSES)[number] | "UNKNOWN";
/** 사용자가 고를 수 있는 제외 태그 (FR-TXN-05). EMERGENCY 는 비상금 기능 연동 전까지 서버가 받지 않는다(노션 명세, 2026-09-15) */
export type UserExcludeTag = "DUTCH" | "SELF_TRANSFER";

/**
 * GET /transactions · /transactions/pending 항목 (백엔드 develop 2026-09-15 대조).
 * 미확정(PENDING)·제외 태그 거래는 봉투·세분류가 null 이다 — 서버는 미확정 거래에 제안 세분류를 주지 않는다.
 */
export type TransactionDto = {
  id: number;
  txType: string;
  merchantName: string | null;
  amount: number;
  /** "YYYY-MM-DD" */
  txDate: string;
  /** "HH:mm:ss" */
  txTime: string;
  envelopeId: number | null;
  subcategoryId: number | null;
  subcategoryName: string | null;
  confirmStatus: string;
  excludeTag: string;
  status: string;
  memo?: string | null;
  /** 계좌 거래만 */
  accountId?: number | null;
  /** 카드 거래만 */
  cardId?: number | null;
  /** 더치페이의 실제 부담액(원). DUTCH 가 아니면 null */
  adjustedAmount?: number | null;
};

export type PendingTransactionsDto = { items: TransactionDto[]; nextCursor: number | null };
/**
 * GET /subcategories 응답. 서버는 **봉투별로 묶어서** 준다 (백엔드 SubcategoryListResponse, 2026-09-16 대조).
 * 화면은 평탄한 목록을 쓰고 시트에서 다시 봉투로 묶으므로 toSubcategories 가 펴 준다.
 */
export type SubcategoryListDto = { items: SubcategoryEnvelopeDto[] };
export type SubcategoryEnvelopeDto = { envelopeId: number; envelopeName: string; subcategories: { id: number; name: string }[] };

/**
 * PUT /transactions/{id}/classification 요청. subcategoryId 와 excludeTag 중 하나만 보내고,
 * DUTCH 는 실제 부담액(adjustedAmount, 1 이상·거래 금액 이하)이 필수다(400 TRANSACTION_008).
 */
export type ClassifyRequest = { subcategoryId: number } | { excludeTag: "SELF_TRANSFER" } | { excludeTag: "DUTCH"; adjustedAmount: number };

/**
 * 더치페이 부담액 입력이 보낼 수 있는 값인지. 서버 규칙(0 초과, 원거래 금액 이하)을 보내기 전에 같은 기준으로 본다.
 * 통과하면 null, 아니면 사용자 문구.
 */
export function dutchAmountError(digits: string, transactionAmount: KRW): string | null {
  if (digits === "" || toWon(digits) <= 0n) return "내가 낸 금액을 입력해 주세요.";
  if (compareKRW(digits, transactionAmount) > 0) return `결제 금액 ${formatKRW(transactionAmount)}을 넘을 수 없어요.`;
  return null;
}

export function toDutchRequest(digits: string): ClassifyRequest {
  return { excludeTag: "DUTCH", adjustedAmount: Number(toWon(digits)) };
}
/** 응답에 봉투 잔액은 없다(예전 계약 사본의 envelopeBalance 는 폐기). 잔액은 예산 조회를 다시 받는다 */
export type ClassifyResponseDto = {
  transactionId: number;
  subcategoryId: number | null;
  excludeTag: string;
  adjustedAmount: number | null;
  confirmStatus: string;
};

export type Transaction = {
  id: number;
  txType: TxType;
  /** 가맹점명 또는 거래 원문. 서버가 비워 보내면 null */
  merchantName: string | null;
  amount: KRW;
  txDate: string;
  txTime: string;
  /** txDate 에서 뽑은 "YYYYMM" — 예산 캐시 키 */
  monthKey: string;
  /** 미확정·제외 태그 거래는 null */
  envelopeId: number | null;
  subcategoryId: number | null;
  subcategoryName: string | null;
  confirmStatus: ConfirmStatus;
  excludeTag: ExcludeTag;
  status: TxStatus;
  memo: string | null;
  accountId: number | null;
  cardId: number | null;
  adjustedAmount: KRW | null;
};

export type PendingTransactions = { items: Transaction[]; nextCursor: number | null };
export type Subcategory = { id: number; name: string; envelopeId: number; envelopeName: string };
export type ClassifyResult = { confirmStatus: ConfirmStatus; subcategoryId: number | null; excludeTag: ExcludeTag; adjustedAmount: KRW | null };

const TX_DATE = /^(\d{4})-(\d{2})-\d{2}$/;

function pick<T extends string>(values: readonly T[], raw: string): T | "UNKNOWN" {
  return (values as readonly string[]).includes(raw) ? (raw as T) : "UNKNOWN";
}

function won(value: number, field: string): KRW {
  try {
    return fromServerWon(value);
  } catch {
    throw new ContractMismatchError(field);
  }
}

export function toTransaction(dto: TransactionDto): Transaction {
  const date = TX_DATE.exec(dto.txDate);
  if (!date) throw new ContractMismatchError("txDate");
  return {
    id: dto.id,
    txType: pick(TX_TYPES, dto.txType),
    merchantName: dto.merchantName,
    amount: won(dto.amount, "amount"),
    txDate: dto.txDate,
    txTime: dto.txTime,
    monthKey: `${date[1]}${date[2]}`,
    envelopeId: dto.envelopeId ?? null,
    subcategoryId: dto.subcategoryId ?? null,
    subcategoryName: dto.subcategoryName ?? null,
    confirmStatus: pick(CONFIRM_STATUSES, dto.confirmStatus),
    excludeTag: pick(EXCLUDE_TAGS, dto.excludeTag),
    status: pick(TX_STATUSES, dto.status),
    memo: dto.memo ?? null,
    accountId: dto.accountId ?? null,
    cardId: dto.cardId ?? null,
    adjustedAmount: dto.adjustedAmount === null || dto.adjustedAmount === undefined ? null : won(dto.adjustedAmount, "adjustedAmount"),
  };
}

/** 가맹점명이 없는 거래(계좌 원문 없음)의 표시 이름 */
export const UNNAMED_MERCHANT_LABEL = "이름 없는 거래";
/** 봉투·세분류가 아직 없는 거래의 표시 */
export const UNCLASSIFIED_LABEL = "미분류";

export function merchantLabel(transaction: Transaction): string {
  return transaction.merchantName ?? UNNAMED_MERCHANT_LABEL;
}

export function toPendingTransactions(dto: PendingTransactionsDto): PendingTransactions {
  return { items: dto.items.map(toTransaction), nextCursor: dto.nextCursor };
}

/**
 * GET /transactions 필터 (FR-TXN-09). month 는 필수고 계좌·카드는 둘 중 하나만 건다.
 * 값이 없는 필터는 키를 빼서 둔다 — 쿼리 키가 같은 필터에서 늘 같아야 캐시가 겹친다.
 */
export type TransactionFilter = {
  /** "YYYYMM" */
  month: string;
  envelopeId?: number;
  accountId?: number;
  cardId?: number;
};

export type TransactionListDto = { items: TransactionDto[]; nextCursor: number | null };
export type TransactionPage = { items: Transaction[]; nextCursor: number | null };

export function toTransactionPage(dto: TransactionListDto): TransactionPage {
  return { items: dto.items.map(toTransaction), nextCursor: dto.nextCursor };
}

/** 들어온 돈은 입금뿐이다. 이체(TRANSFER)는 방향이 계약에 없어 나간 돈으로 둔다 (TBD) */
export function isIncoming(transaction: Transaction): boolean {
  return transaction.txType === "DEPOSIT";
}

/** 목록의 "날짜 · 분류" 자리. 입금은 세분류 대신 "입금", 세분류가 아직 없으면 "미분류" 라고 쓴다 */
export function transactionCategoryLabel(transaction: Transaction): string {
  if (isIncoming(transaction)) return "입금";
  return transaction.subcategoryName ?? UNCLASSIFIED_LABEL;
}

const EXCLUDE_TAG_LABELS: Partial<Record<ExcludeTag, string>> = {
  DUTCH: "더치페이",
  SELF_TRANSFER: "내 계좌 이동",
  EMERGENCY: "비상금",
  CARRYOVER: "이월",
  RESTORE: "환급",
};

/** 취소·예산 제외 거래도 숨기지 않고 뱃지로 알린다(FR-TXN-09). 취소가 먼저다 */
export function transactionBadge(transaction: Transaction): string | null {
  if (transaction.status === "CANCELED") return "취소";
  return EXCLUDE_TAG_LABELS[transaction.excludeTag] ?? null;
}

/** 거래 상세(PAGE-21)의 거래 종류 자리. 계약에 없는 값은 "기타" 로 적는다 */
const TX_TYPE_LABELS: Record<TxType, string> = {
  CARD: "카드 결제",
  DEPOSIT: "입금",
  WITHDRAW: "계좌 출금",
  TRANSFER: "이체",
  CARD_BILL: "카드대금",
  UNKNOWN: "기타",
};

export function txTypeLabel(transaction: Transaction): string {
  return TX_TYPE_LABELS[transaction.txType];
}

/** 분류 상태 자리. 모르는 값은 자리를 비운다 */
const CONFIRM_STATUS_LABELS: Partial<Record<ConfirmStatus, string>> = {
  AUTO: "자동 분류",
  PENDING: "확인 필요",
  CONFIRMED: "확인 완료",
};

export function confirmStatusLabel(transaction: Transaction): string | null {
  return CONFIRM_STATUS_LABELS[transaction.confirmStatus] ?? null;
}

/** 거래 상세의 "2026.09.08 14:21". 서버는 날짜·시각을 따로 주므로 합쳐 읽고, 시각 형식이 틀리면 날짜만 쓴다 */
export function transactionDateTimeLabel(transaction: Transaction): string {
  const dateTime = `${transaction.txDate}T${transaction.txTime}`;
  return KST_LOCAL_DATE_TIME.test(dateTime)
    ? formatDateTime(parseKSTLocalDateTime(dateTime))
    : formatDate(parseKSTDateKey(transaction.txDate));
}

/**
 * 분류를 바꿀 수 없는 거래의 이유. 바꿀 수 있으면 null (FR-TXN-03·05).
 * 서버도 같은 규칙이다 — 입금(DEPOSIT)과 취소(CANCELED)는 409 TRANSACTION_007 로 막는다
 * (Transaction.validateClassifiable, 2026-09-16 대조). 화면은 그 전에 버튼을 잠가 헛걸음을 줄인다.
 * 환급 입금을 봉투로 되돌리는 RESTORE 는 서버가 입금에만 허용하는데 화면 입력이 아직 없다 (TBD)
 */
export function reclassifyBlockedReason(transaction: Transaction): string | null {
  if (transaction.status === "CANCELED") return "취소된 결제는 분류를 바꿀 수 없어요.";
  if (isIncoming(transaction)) return "입금은 봉투에 들어가지 않아 분류가 없어요.";
  return null;
}

const MONTH_KEY = /^(\d{4})(0[1-9]|1[0-2])$/;
const POSITIVE_ID = /^[1-9]\d*$/;
/** "202609" → "2026년 9월" */
export function monthFilterLabel(key: string): string {
  const matched = MONTH_KEY.exec(key);
  return matched ? `${matched[1]}년 ${Number(matched[2])}월` : key;
}

type SearchParams = Record<string, string | string[] | undefined>;

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function idParam(value: string | string[] | undefined): number | undefined {
  const raw = firstParam(value);
  return raw !== undefined && POSITIVE_ID.test(raw) ? Number(raw) : undefined;
}

/**
 * 거래 내역 화면의 검색 파라미터를 필터로 바꾼다. 라우트 파라미터는 믿지 않고 형식이 틀리면 버린다.
 * 달이 없거나 틀리거나 미래면 이번 달로, 계좌와 카드가 둘 다 오면 계좌만 쓴다.
 */
export function parseTransactionFilter(params: SearchParams, currentMonth: string): TransactionFilter {
  const month = firstParam(params.month);
  const filter: TransactionFilter = {
    month: month !== undefined && MONTH_KEY.test(month) && month <= currentMonth ? month : currentMonth,
  };
  const envelopeId = idParam(params.envelopeId);
  const accountId = idParam(params.accountId);
  const cardId = accountId === undefined ? idParam(params.cardId) : undefined;
  if (envelopeId !== undefined) filter.envelopeId = envelopeId;
  if (accountId !== undefined) filter.accountId = accountId;
  if (cardId !== undefined) filter.cardId = cardId;
  return filter;
}

/** 거래 상세 라우트(`/transaction/[id]`)의 id. 양의 정수가 아니면 null — 라우트 파라미터는 믿지 않는다 */
export function parseTransactionId(value: string | string[] | undefined): number | null {
  const raw = firstParam(value);
  return raw !== undefined && POSITIVE_ID.test(raw) ? Number(raw) : null;
}

/** 봉투 묶음을 펴서 세분류 목록으로. 봉투 순서·세분류 순서는 서버가 준 대로 둔다 */
export function toSubcategories(dto: SubcategoryListDto): Subcategory[] {
  return dto.items.flatMap((envelope) =>
    envelope.subcategories.map((item) => ({
      id: item.id,
      name: item.name,
      envelopeId: envelope.envelopeId,
      envelopeName: envelope.envelopeName,
    }))
  );
}

export function toClassifyResult(dto: ClassifyResponseDto): ClassifyResult {
  return {
    confirmStatus: pick(CONFIRM_STATUSES, dto.confirmStatus),
    subcategoryId: dto.subcategoryId ?? null,
    excludeTag: pick(EXCLUDE_TAGS, dto.excludeTag),
    adjustedAmount: dto.adjustedAmount === null || dto.adjustedAmount === undefined ? null : won(dto.adjustedAmount, "adjustedAmount"),
  };
}

/* ───────────── 일괄 확정: PUT /transactions/classifications (배포 서버 Swagger 2026-09-20 대조, FR-TXN-03 P1) ───────────── */

/**
 * 정리 세션에서 여러 건을 한 번에 확정한다. 한 건이라도 실패하면 서버가 전체를 되돌리므로 부분 성공은 없다.
 * 한 요청에 100건까지고, 넘기면 400 COMMON_001 이다. 항목은 단건 확정과 같은 조합 규칙을 따른다
 * (일반 소비는 subcategoryId, DUTCH 는 adjustedAmount, 내 계좌 이동 등은 excludeTag).
 */
export const BULK_CLASSIFY_MAX = 100;

export type BulkClassifyItemDto = {
  transactionId: number;
  subcategoryId?: number | null;
  excludeTag?: string | null;
  adjustedAmount?: number | null;
};

export type BulkClassifyRequest = { items: BulkClassifyItemDto[] };

export type BulkClassifyResultDto = { confirmed: number; pendingRemain: number };

/** confirmed: 확정한 건수 · pendingRemain: 처리 뒤 서버에 남은 미확정 건수(받아 둔 쪽과 무관한 전체 수다) */
export type BulkClassifyResult = { confirmed: number; pendingRemain: number };

function count(value: number, field: string): number {
  if (!Number.isSafeInteger(value) || value < 0) throw new ContractMismatchError(field);
  return value;
}

export function toBulkClassifyResult(dto: BulkClassifyResultDto): BulkClassifyResult {
  return { confirmed: count(dto.confirmed, "confirmed"), pendingRemain: count(dto.pendingRemain, "pendingRemain") };
}

/** 제안 세분류가 있어 한 번에 확정할 수 있는 거래. 제안이 없는 건은 고를 것이 없어 빠진다 */
/**
 * 알림에서 넘어온 거래를 미확정 목록에서 찾은 결과 (알림함·푸시 → PAGE-22, 2026-09-21).
 * 거래 단건 조회 API 가 없어서(GET /transactions/{id} 없음) 거래 상세로 바로 보내면 캐시에 없을 때 "찾을 수 없어요"가 된다.
 * 미확정 목록은 이 화면이 직접 받으므로 여기서 찾는다.
 * - found: 찾았다. 그 거래의 분류 창을 연다
 * - searching: 받은 쪽에는 없고 더 받을 쪽이 남았다. 다음 쪽을 받아 다시 찾는다
 * - gone: 끝까지 받았는데 없다 = 이미 정리한 거래다(다른 기기·자동 분류 포함). 목록만 보여 주고 그렇다고 알린다
 */
export type PendingFocus = { state: "found"; transaction: Transaction } | { state: "searching" } | { state: "gone" };

export function resolvePendingFocus(transactions: readonly Transaction[], focusId: number, hasNextPage: boolean): PendingFocus {
  const transaction = transactions.find((candidate) => candidate.id === focusId);
  if (transaction !== undefined) return { state: "found", transaction };
  return hasNextPage ? { state: "searching" } : { state: "gone" };
}

/** 라우트 파라미터(문자열)를 거래 id 로. 양의 정수 모양이 아니면 null 이라 평소 진입과 같아진다 (규칙 50: 딥링크 값은 믿지 않는다) */
export function toFocusTransactionId(raw: unknown): number | null {
  if (typeof raw !== "string" || !/^[1-9]\d*$/.test(raw)) return null;
  const id = Number(raw);
  return Number.isSafeInteger(id) ? id : null;
}

export function suggestedForBulk(transactions: readonly Transaction[]): Transaction[] {
  return transactions.filter((transaction) => transaction.subcategoryId !== null).slice(0, BULK_CLASSIFY_MAX);
}

/** 제안대로 확정할 요청. 제안이 없는 건은 빠지고 100건을 넘으면 앞에서부터 자른다 */
export function toSuggestedBulkRequest(transactions: readonly Transaction[]): BulkClassifyRequest {
  return {
    items: suggestedForBulk(transactions).map((transaction) => ({
      transactionId: transaction.id,
      subcategoryId: transaction.subcategoryId,
    })),
  };
}
