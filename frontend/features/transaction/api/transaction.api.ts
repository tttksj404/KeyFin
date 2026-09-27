import { api, isMocked } from "@/api/client";
import { withMockLatency } from "@/api/mocks/latency";
import {
  classifyTransactionMock,
  classifyTransactionsBulkMock,
  pendingTransactionsMock,
  subcategoriesMock,
  transactionListMock,
} from "@/api/mocks/transaction";
import {
  toBulkClassifyResult,
  toClassifyResult,
  toPendingTransactions,
  toSubcategories,
  toTransactionPage,
  type BulkClassifyRequest,
  type BulkClassifyResult,
  type BulkClassifyResultDto,
  type ClassifyRequest,
  type ClassifyResponseDto,
  type ClassifyResult,
  type PendingTransactions,
  type PendingTransactionsDto,
  type Subcategory,
  type SubcategoryListDto,
  type TransactionFilter,
  type TransactionListDto,
  type TransactionPage,
} from "@/features/transaction/model";
import { currentDateKey } from "@/lib/date";

export type TransactionPageParams = { cursor: number | null; size: number };

/**
 * GET /transactions — 월 거래 목록, 커서 페이지 (FR-TXN-09). 취소·예산 제외 거래도 온다.
 * 백엔드 develop 구현과 대조 완료(2026-09-16): 정렬은 거래일·시각·id 내림차순이고 커서도 그 셋의 키셋이라 쪽이 겹치거나 빠지지 않는다.
 */
export async function getTransactions(
  filter: TransactionFilter,
  { cursor, size }: TransactionPageParams,
  signal?: AbortSignal
): Promise<TransactionPage> {
  const params = { ...filter, cursor: cursor ?? undefined, size };
  if (isMocked("transaction")) return toTransactionPage(await withMockLatency(transactionListMock(params, currentDateKey()), signal));
  const { data } = await api.get<TransactionListDto>("/transactions", { params, signal });
  return toTransactionPage(data);
}

/**
 * GET /transactions/pending?cursor=&size= — 사용자 확인이 필요한 미확정 거래, 커서 페이지 (FR-TXN-03).
 * 서버는 PENDING·NORMAL·입금 제외를 최신순으로 주고 size 기본 20 이다(백엔드 findPendingTransactions, 2026-09-16 대조).
 */
export async function getPendingTransactions({ cursor, size }: TransactionPageParams, signal?: AbortSignal): Promise<PendingTransactions> {
  if (isMocked("transaction")) return toPendingTransactions(await withMockLatency(pendingTransactionsMock(cursor, size), signal));
  const { data } = await api.get<PendingTransactionsDto>("/transactions/pending", { params: { cursor: cursor ?? undefined, size }, signal });
  return toPendingTransactions(data);
}

/** GET /subcategories — 정적 세분류 22종 */
export async function getSubcategories(signal?: AbortSignal): Promise<Subcategory[]> {
  if (isMocked("transaction")) return toSubcategories(await withMockLatency(subcategoriesMock, signal));
  const { data } = await api.get<SubcategoryListDto>("/subcategories", { signal });
  return toSubcategories(data);
}

export type ClassifyInput = { transactionId: number; request: ClassifyRequest };

/** PUT /transactions/{id}/classification — 세분류 확정 또는 제외 태그. 응답에 봉투 잔액은 없어 잔액은 예산 조회로 다시 받는다 */
export async function classifyTransaction({ transactionId, request }: ClassifyInput): Promise<ClassifyResult> {
  if (isMocked("transaction")) return toClassifyResult(await withMockLatency(classifyTransactionMock(transactionId, request)));
  const { data } = await api.put<ClassifyResponseDto>(`/transactions/${transactionId}/classification`, request);
  return toClassifyResult(data);
}

/**
 * PUT /transactions/classifications — 여러 건을 한 번에 확정한다 (FR-TXN-03, P1).
 * 한 건이라도 실패하면 서버가 전체를 되돌린다. 오류: 400 COMMON_001·TRANSACTION_006·008 · 404 TRANSACTION_004~005 · 409 TRANSACTION_007.
 */
export async function classifyTransactionsBulk(request: BulkClassifyRequest): Promise<BulkClassifyResult> {
  if (isMocked("transaction")) return toBulkClassifyResult(await withMockLatency(classifyTransactionsBulkMock(request)));
  const { data } = await api.put<BulkClassifyResultDto>("/transactions/classifications", request);
  return toBulkClassifyResult(data);
}
