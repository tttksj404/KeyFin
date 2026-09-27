import {
  infiniteQueryOptions,
  type InfiniteData,
  queryOptions,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { accountKeys } from "@/features/account/api/queries";
import { isStaleAccountError } from "@/features/account/errors";
import {
  assignFixedExpenseCard,
  approveTransfer,
  createFixedExpense,
  deleteFixedExpense,
  getCardBillingDetail,
  getCardBillings,
  getFixedExpenses,
  getPaymentCalendar,
  getTransfer,
  getTransfers,
  postponeTransfer,
  TRANSFER_PAGE_SIZE,
  updateFixedExpense,
  type TransferListParams,
} from "@/features/payment/api/payment.api";
import { isCardNotFoundError, isStaleCardError, isStaleFixedExpenseError } from "@/features/payment/errors";
import { findFixedExpense, type Transfer, type TransferPage } from "@/features/payment/model";
import { roomKeys } from "@/features/room/api/queries";

export const paymentKeys = {
  all: ["payment"] as const,
  /** 고정지출·이체 변경 시 달 구분 없이 무효화하는 키 (docs/api-guide.md §무효화) */
  calendar: () => [...paymentKeys.all, "calendar"] as const,
  calendarMonth: (month: string) => [...paymentKeys.calendar(), month] as const,
  /** 활성 고정지출 목록(GET /fixed-expenses). 관리 화면과 수정 화면이 같이 쓴다 */
  fixedExpenses: () => [...paymentKeys.all, "fixed-expenses"] as const,
  /** 카드별 청구 요약. 주기를 서버가 정해 파라미터가 없다 */
  cardBillings: () => [...paymentKeys.all, "card-billings"] as const,
  /** 카드 한 장의 청구 상세. card-billings 프리픽스 아래라 카드 연결·해제 뒤 요약과 함께 무효화된다 */
  cardBillingDetail: (cardId: number) => [...paymentKeys.cardBillings(), "detail", cardId] as const,
  /** 이체 제안·이력. 승인·연기 뒤 달 구분 없이 무효화한다 */
  transfers: () => [...paymentKeys.all, "transfers"] as const,
  transferList: (params: TransferListParams) => [...paymentKeys.transfers(), "list", params] as const,
  /** 단건(GET /transfers/{id}). transfers 프리픽스 아래라 승인·연기 뒤 목록과 함께 무효화된다 */
  transfer: (transferId: number) => [...paymentKeys.transfers(), "detail", transferId] as const,
};

export function paymentCalendarQueryOptions(month: string) {
  return queryOptions({
    queryKey: paymentKeys.calendarMonth(month),
    queryFn: ({ signal }) => getPaymentCalendar(month, signal),
    staleTime: 30_000,
  });
}

export function usePaymentCalendar(month: string) {
  return useQuery(paymentCalendarQueryOptions(month));
}

export function fixedExpensesQueryOptions() {
  return queryOptions({
    queryKey: paymentKeys.fixedExpenses(),
    queryFn: ({ signal }) => getFixedExpenses(signal),
    staleTime: 30_000,
  });
}

/** 고정지출 관리 화면의 목록 */
export function useFixedExpenses() {
  return useQuery(fixedExpensesQueryOptions());
}

/**
 * 고정지출 수정 화면(PAGE-26)의 한 건. 단건 조회 API 가 없어 목록 조회에서 고른다(관리 화면과 캐시를 나눠 쓴다).
 * 목록에 없으면(이미 삭제됨·잘못된 주소) data 가 null 이다.
 */
export function useFixedExpense(fixedExpenseId: number | null) {
  return useQuery({
    ...fixedExpensesQueryOptions(),
    enabled: fixedExpenseId !== null,
    select: (expenses) => (fixedExpenseId === null ? null : findFixedExpense(expenses, fixedExpenseId)),
  });
}

/**
 * 고정지출을 바꾸면 목록과, 달 구분 없이 캘린더를 무효화한다(출금일을 옮기면 다른 달로 갈 수 있다).
 * 이체 제안이 고정지출을 참조하고 방 캘린더 에셋도 캘린더 조회를 쓰므로 둘 다 함께 무효화한다 (docs/api-guide.md §5).
 * 이미 삭제됐거나 동기화 항목이라 거절되면(PAY_001·002) 화면이 낡은 것이라 같은 범위를, 계좌 오류(ACCOUNT_001·002)면 계좌 목록을 다시 받는다.
 */
function useFixedExpenseMutation<TVariables>(mutationFn: (variables: TVariables) => Promise<unknown>) {
  const queryClient = useQueryClient();
  const refreshSchedules = () => {
    void queryClient.invalidateQueries({ queryKey: paymentKeys.fixedExpenses() });
    void queryClient.invalidateQueries({ queryKey: paymentKeys.calendar() });
    void queryClient.invalidateQueries({ queryKey: paymentKeys.transfers() });
    void queryClient.invalidateQueries({ queryKey: roomKeys.all });
  };
  return useMutation({
    mutationFn,
    onSuccess: refreshSchedules,
    onError: (error) => {
      if (isStaleFixedExpenseError(error)) refreshSchedules();
      if (isStaleAccountError(error)) void queryClient.invalidateQueries({ queryKey: accountKeys.all });
    },
  });
}

export function useCreateFixedExpense() {
  return useFixedExpenseMutation(createFixedExpense);
}

export function useUpdateFixedExpense() {
  return useFixedExpenseMutation(updateFixedExpense);
}

export function useDeleteFixedExpense() {
  return useFixedExpenseMutation(deleteFixedExpense);
}

/**
 * 정기결제 결제 카드 지정(-183). 캘린더·이체에는 영향이 없어 고정지출 목록만 다시 받는다.
 * 카드가 없거나 연결 해제됐으면(PAY_013·015) 카드 목록을, 항목이 사라졌으면(PAY_001) 고정지출 목록을 다시 받는다.
 */
export function useAssignFixedExpenseCard() {
  const queryClient = useQueryClient();
  const refreshExpenses = () => queryClient.invalidateQueries({ queryKey: paymentKeys.fixedExpenses() });
  return useMutation({
    mutationFn: assignFixedExpenseCard,
    onSuccess: refreshExpenses,
    onError: (error) => {
      if (isStaleFixedExpenseError(error)) void refreshExpenses();
      if (isStaleCardError(error)) void queryClient.invalidateQueries({ queryKey: paymentKeys.cardBillings() });
    },
  });
}

/** 커서 페이지(-62). 결제 캘린더는 해당 달(dueDate 기준)로 좁혀 첫 쪽만으로 부족 뱃지를 잇는다 */
export function transferListQueryOptions(params: TransferListParams) {
  return infiniteQueryOptions({
    queryKey: paymentKeys.transferList(params),
    queryFn: ({ pageParam, signal }) => getTransfers(params, { cursor: pageParam, size: TRANSFER_PAGE_SIZE }, signal),
    initialPageParam: null as number | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    staleTime: 30_000,
  });
}

export function useTransfers(params: TransferListParams) {
  return useInfiniteQuery(transferListQueryOptions(params));
}

/** 받아 둔 쪽들을 한 목록으로 */
export function flattenTransfers(data: InfiniteData<TransferPage> | undefined): Transfer[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}

/** 이체 승인 화면(PAGE-25)의 단건 조회(GET /transfers/{id}). 승인·연기 뒤 transfers 프리픽스로 같이 무효화된다 */
export function transferQueryOptions(transferId: number) {
  return queryOptions({
    queryKey: paymentKeys.transfer(transferId),
    queryFn: ({ signal }) => getTransfer(transferId, signal),
    staleTime: 30_000,
  });
}

export function useTransfer(transferId: number | null) {
  return useQuery({ ...transferQueryOptions(transferId ?? 0), enabled: transferId !== null });
}

/**
 * 승인은 돈이 실제로 움직인다 (규칙 80): 자동 재시도를 끄고, 성공하면 제안 목록과 결제 캘린더(준비 상태)를 다시 받는다.
 * 네트워크 오류로 결과를 모를 때도 목록을 다시 받아 서버 상태로 확정한다.
 */
export function useApproveTransfer() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: paymentKeys.transfers() });
    void queryClient.invalidateQueries({ queryKey: paymentKeys.calendar() });
    void queryClient.invalidateQueries({ queryKey: roomKeys.all });
  };
  return useMutation({ mutationFn: approveTransfer, retry: false, onSuccess: invalidate, onError: invalidate });
}

/** 연기는 제안을 PROPOSED 로 남긴다. 목록만 다시 받는다 */
export function usePostponeTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: postponeTransfer,
    retry: false,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentKeys.transfers() }),
  });
}

export function cardBillingsQueryOptions() {
  return queryOptions({
    queryKey: paymentKeys.cardBillings(),
    queryFn: ({ signal }) => getCardBillings(signal),
    staleTime: 60_000,
  });
}

/** 자산 탭 카드 섹션이 쓴다. 카드 이름·번호는 금융망 후보에서 오고 금액만 이 조회로 채운다 */
export function useCardBillings() {
  return useQuery(cardBillingsQueryOptions());
}

const MAX_CARD_BILLING_DETAIL_RETRY = 1;

/** 없는 카드(404 PAY_013)는 다시 불러도 같으므로 재시도하지 않고 바로 '못 찾음' 을 보여 준다 */
export function cardBillingDetailQueryOptions(cardId: number) {
  return queryOptions({
    queryKey: paymentKeys.cardBillingDetail(cardId),
    queryFn: ({ signal }) => getCardBillingDetail(cardId, signal),
    staleTime: 60_000,
    retry: (failureCount, error) => !isCardNotFoundError(error) && failureCount < MAX_CARD_BILLING_DETAIL_RETRY,
  });
}

/** 카드 청구 상세(PAGE-33). 라우트의 카드 id 가 틀리면(null) 조회하지 않는다 */
export function useCardBillingDetail(cardId: number | null) {
  return useQuery({ ...cardBillingDetailQueryOptions(cardId ?? 0), enabled: cardId !== null });
}
