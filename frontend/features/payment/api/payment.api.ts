import { TIMEOUT_MONEY_MS, api, isMocked } from "@/api/client";
import { withMockLatency } from "@/api/mocks/latency";
import {
  assignFixedExpenseCardMock,
  cardBillingDetailMock,
  cardBillingsMock,
  createFixedExpenseMock,
  deleteFixedExpenseMock,
  fixedExpenseListMock,
  paymentCalendarMock,
  updateFixedExpenseMock,
} from "@/api/mocks/payment";
import { approveTransferMock, postponeTransferMock, transferDetailMock, transferListMock } from "@/api/mocks/transfer";
import {
  toCardBillingDetail,
  toCardBillings,
  toFixedExpenses,
  toPaymentCalendar,
  toTransferDetail,
  toTransferPage,
  type ApproveTransferDto,
  type FixedExpense,
  type FixedExpenseListDto,
  type FixedExpenseRequest,
  type FixedExpenseResponseDto,
  type CardBillingDetail,
  type CardBillingDetailDto,
  type CardBillings,
  type CardBillingsDto,
  type PaymentCalendar,
  type PaymentCalendarDto,
  type TransferDetail,
  type TransferDetailDto,
  type TransferListDto,
  type TransferPage,
  type TransferStatus,
} from "@/features/payment/model";
import { currentMonthKey, serverClock, toKSTDateKey } from "@/lib/date";

/**
 * GET /payments/calendar?month=YYYYMM — 날짜별 출금 예정과 준비 상태 (docs/api-contract.md PAYMENT, FR-PAY-01·02).
 * 금융망 정기결제·카드 청구 동기화는 호출 시가 아니라 서버 스케줄러(08:00·17:00 KST)가 한다(develop 69fdacb) — 조회는 저장된 값이다.
 */
export async function getPaymentCalendar(month: string, signal?: AbortSignal): Promise<PaymentCalendar> {
  if (isMocked("payment")) return toPaymentCalendar(await withMockLatency(paymentCalendarMock(month), signal));
  const { data } = await api.get<PaymentCalendarDto>("/payments/calendar", { params: { month }, signal });
  return toPaymentCalendar(data);
}

/** GET /fixed-expenses — 활성 고정지출을 등록 순으로. 동기화 항목(synced)도 섞여 온다 (FR-PAY-07) */
export async function getFixedExpenses(signal?: AbortSignal): Promise<FixedExpense[]> {
  if (isMocked("payment")) return toFixedExpenses(await withMockLatency(fixedExpenseListMock(), signal));
  const { data } = await api.get<FixedExpenseListDto>("/fixed-expenses", { signal });
  return toFixedExpenses(data);
}

/** POST /fixed-expenses — 201 (FR-PAY-07). 응답은 새 id 뿐이라 화면은 목록·캘린더를 다시 받는다 */
export async function createFixedExpense(request: FixedExpenseRequest): Promise<number> {
  if (isMocked("payment")) return (await withMockLatency(createFixedExpenseMock(request))).id;
  const { data } = await api.post<FixedExpenseResponseDto>("/fixed-expenses", request);
  return data.id;
}

export type UpdateFixedExpenseInput = { id: number; request: FixedExpenseRequest };

/** PUT /fixed-expenses/{id} — 등록과 같은 본문 전체로 교체한다(부분 수정 없음). 동기화 항목은 409 PAY_002 */
export async function updateFixedExpense({ id, request }: UpdateFixedExpenseInput): Promise<number> {
  if (isMocked("payment")) return (await withMockLatency(updateFixedExpenseMock(id, request))).id;
  const { data } = await api.put<FixedExpenseResponseDto>(`/fixed-expenses/${id}`, request);
  return data.id;
}

export type AssignFixedExpenseCardInput = { id: number; cardId: number };

/**
 * PATCH /fixed-expenses/{id}/card — 금융망 정기결제(synced)의 결제 카드 지정 (-183). 다시 부르면 카드를 바꾼다.
 * 오류: 404 PAY_001(없음·타인) · 404 PAY_013(카드 없음·타인) · 409 PAY_014(수동 항목) · 409 PAY_015(미관리 카드).
 */
export async function assignFixedExpenseCard({ id, cardId }: AssignFixedExpenseCardInput): Promise<number> {
  if (isMocked("payment")) return (await withMockLatency(assignFixedExpenseCardMock(id, cardId))).id;
  const { data } = await api.patch<FixedExpenseResponseDto>(`/fixed-expenses/${id}/card`, { cardId });
  return data.id;
}

/** DELETE /fixed-expenses/{id} — data 는 null. 서버는 비활성으로 바꾸고 앞으로의 일정에서 뺀다 */
export async function deleteFixedExpense(id: number): Promise<void> {
  if (isMocked("payment")) {
    await withMockLatency(deleteFixedExpenseMock(id));
    return;
  }
  await api.delete(`/fixed-expenses/${id}`);
}

export type TransferListParams = {
  /** 생략하면 전체 상태 */
  status?: TransferStatus;
  /** "YYYYMM" — 대상 출금일(dueDate) 기준. 생략하면 전체 기간 */
  month?: string;
};

export type TransferPageParams = { cursor: number | null; size: number };

/** 계약 기본값(size 20)과 같다 */
export const TRANSFER_PAGE_SIZE = 20;

/**
 * GET /transfers?status=&month=&cursor=&size= — 준비 이체 제안·이력, 커서 페이지 (FR-PAY-03·08, -62 2026-09-16).
 * 최신순(id 내림차순), 커서는 마지막 항목 id. 값이 틀리면 400 COMMON_001.
 */
export async function getTransfers(filter: TransferListParams, page: TransferPageParams, signal?: AbortSignal): Promise<TransferPage> {
  if (isMocked("payment")) return toTransferPage(await withMockLatency(transferListMock(currentMonthKey(), filter, page), signal));
  const { data } = await api.get<TransferListDto>("/transfers", {
    params: { status: filter.status, month: filter.month, cursor: page.cursor ?? undefined, size: page.size },
    signal,
  });
  return toTransferPage(data);
}

/** GET /transfers/{id} — 제안 한 건 + 감사 타임라인 (-62). 없거나 남의 것이면 404 PAY_005 */
export async function getTransfer(transferId: number, signal?: AbortSignal): Promise<TransferDetail> {
  if (isMocked("payment")) return toTransferDetail(await withMockLatency(transferDetailMock(currentMonthKey(), transferId), signal));
  const { data } = await api.get<TransferDetailDto>(`/transfers/${transferId}`, { signal });
  return toTransferDetail(data);
}

export type ApproveTransferResult = { id: number; status: TransferStatus; executedAt: string | null };

/**
 * POST /transfers/{id}/approve — 돈이 실제로 움직인다.
 * 중복 실행은 서버가 기관거래고유번호로 막고(계약에 멱등성 키 없음, 규칙 90) 클라이언트는 같은 제안 id 로만 보낸다.
 * 자동 재시도는 하지 않는다 — 실패·미확인은 화면이 상태 조회로 확정한다 (규칙 80).
 */
export async function approveTransfer(transferId: number): Promise<ApproveTransferResult> {
  if (isMocked("payment")) {
    const now = `${toKSTDateKey(new Date(serverClock.now()))}T07:12:00`;
    const mock = await withMockLatency(approveTransferMock(transferId, now));
    return { id: mock.id, status: "EXECUTED", executedAt: mock.executedAt ?? null };
  }
  const { data } = await api.post<ApproveTransferDto>(`/transfers/${transferId}/approve`, undefined, { timeout: TIMEOUT_MONEY_MS });
  return { id: data.id, status: "EXECUTED", executedAt: data.executedAt ?? null };
}

/** POST /transfers/{id}/postpone — 응답 본문 없음. 제안은 PROPOSED 로 남는다 */
export async function postponeTransfer(transferId: number): Promise<void> {
  if (isMocked("payment")) {
    const now = `${toKSTDateKey(new Date(serverClock.now()))}T07:12:30`;
    await withMockLatency(postponeTransferMock(transferId, now));
    return;
  }
  await api.post(`/transfers/${transferId}/postpone`);
}

/**
 * GET /cards/billings — 관리 대상 카드별 이번 주기 승인 합계와 최근 청구서 (docs/api-contract.md PAYMENT, 2026-09-16).
 * 주기는 서버가 정한다(이번 주 월요일~오늘). 카드 이름·번호는 이 응답에 없어 화면이 금융망 후보와 cardId 로 잇는다.
 */
export async function getCardBillings(signal?: AbortSignal): Promise<CardBillings> {
  if (isMocked("payment")) return toCardBillings(await withMockLatency(cardBillingsMock(), signal));
  const { data } = await api.get<CardBillingsDto>("/cards/billings", { signal });
  return toCardBillings(data);
}

/**
 * GET /cards/{cardId}/billings — 카드 한 장의 이번 주기 예정액과 근거 승인 목록, 발행된 청구서 (FR-BGT-06, PAGE-33).
 * from·to 는 보내지 않아 서버 기본값(전월~이번 달)을 쓴다. 본인 카드가 아니거나 없으면 404 PAY_013.
 */
export async function getCardBillingDetail(cardId: number, signal?: AbortSignal): Promise<CardBillingDetail> {
  if (isMocked("payment")) return toCardBillingDetail(await withMockLatency(cardBillingDetailMock(cardId), signal));
  const { data } = await api.get<CardBillingDetailDto>(`/cards/${cardId}/billings`, { signal });
  return toCardBillingDetail(data);
}
