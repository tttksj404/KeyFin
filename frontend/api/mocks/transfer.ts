import type { TransferListParams, TransferPageParams } from "@/features/payment/api/payment.api";
import type { ApproveTransferDto, TransferDetailDto, TransferDto, TransferListDto } from "@/features/payment/model";

type HistoryDto = TransferDetailDto["history"][number];

/**
 * GET /transfers 응답 예시 (docs/api-contract.md PAYMENT · 백엔드 TransferListResponse, -62 2026-09-16).
 * 응답은 `{ items, nextCursor }` 커서 페이지다 — 최신순(id 내림차순), 커서는 마지막 항목 id.
 * 결제 캘린더 목의 15일 월세(fixedExpenseId 11 · 출금 계좌 1 · 부족 230,000)에 맞춘 제안 1건과, 실패 화면 확인용 1건을 둔다.
 * 캘린더 부족 뱃지가 이 제안으로 이어지려면 purpose.fixedExpenseId·dueDate·toAccountId 가 캘린더 목과 같아야 한다(findTransferForEntry).
 * 제안은 08:30 배치가 출금일 하루 전에 만들므로 scheduledDate = dueDate − 1 이다(월요일 출금 카드만 같은 날).
 * 승인하면 서버처럼 상태가 EXECUTED 로 바뀌어 다시 조회할 때 결과가 보인다.
 */
function dateOf(month: string, day: number): string {
  return `${month.slice(0, 4)}-${month.slice(4)}-${String(day).padStart(2, "0")}`;
}

function initial(month: string): TransferDto[] {
  return [
    {
      id: 501,
      status: "PROPOSED",
      scheduledDate: dateOf(month, 14),
      dueDate: dateOf(month, 15),
      requiredAmount: 230000,
      fromAccountId: 2,
      toAccountId: 1,
      purpose: { type: "FIXED", fixedExpenseId: 11, cardBillingId: null, name: "월세" },
      createdAt: `${dateOf(month, 14)}T08:30:12`,
    },
    {
      id: 502,
      status: "FAILED",
      scheduledDate: dateOf(month, 10),
      dueDate: dateOf(month, 10),
      requiredAmount: 55000,
      fromAccountId: 1,
      toAccountId: 2,
      failReason: "출금 계좌 잔액이 부족해 이체하지 못했어요.",
      purpose: { type: "CARD_BILL", fixedExpenseId: null, cardBillingId: 5, name: "통신비" },
      createdAt: `${dateOf(month, 10)}T08:30:09`,
    },
  ];
}

let transfers: TransferDto[] | null = null;
let histories: Map<number, HistoryDto[]> | null = null;

function ensure(month: string): TransferDto[] {
  if (transfers === null) transfers = initial(month);
  return transfers;
}

/** 감사 로그는 오래된 순으로 쌓인다(서버 findAllByTargetTypeAndTargetIdOrderByIdAsc). 근거 문구 모양도 서버를 따른다 */
function ensureHistories(month: string): Map<number, HistoryDto[]> {
  if (histories === null) {
    const failed = ensure(month).find((transfer) => transfer.status === "FAILED");
    histories = new Map();
    if (failed !== undefined) {
      histories.set(failed.id, [
        {
          action: "FAIL",
          basis: `A1014 출금 계좌 잔액 부족 — 기관거래고유번호 2026091000${failed.id}, 금액 ${failed.requiredAmount}`,
          at: `${failed.dueDate}T09:12:00`,
        },
      ]);
    }
  }
  return histories;
}

function appendHistory(month: string, transferId: number, entry: HistoryDto): void {
  const log = ensureHistories(month);
  log.set(transferId, [...(log.get(transferId) ?? []), entry]);
}

/** 서버처럼 status·month(dueDate 기준) 로 거르고 최신순(id 내림차순)으로 커서·size 만큼 자른다 */
export function transferListMock(
  todayMonth: string,
  { status, month }: TransferListParams = {},
  { cursor, size }: TransferPageParams = { cursor: null, size: 20 }
): TransferListDto {
  const filtered = ensure(todayMonth)
    .filter((transfer) => status === undefined || transfer.status === status)
    .filter((transfer) => month === undefined || transfer.dueDate.slice(0, 7).replace("-", "") === month)
    .sort((left, right) => right.id - left.id);
  const start = cursor === null ? 0 : filtered.findIndex((transfer) => transfer.id === cursor) + 1;
  const page = filtered.slice(start, start + size).map((transfer) => ({ ...transfer }));
  const hasNext = start + size < filtered.length;
  return { items: page, nextCursor: hasNext ? (page[page.length - 1]?.id ?? null) : null };
}

/** GET /transfers/{id} — 제안 + 감사 타임라인. 없으면 404 PAY_005 대신 호출부가 잡도록 throw 한다 */
export function transferDetailMock(todayMonth: string, transferId: number): TransferDetailDto {
  const transfer = ensure(todayMonth).find((item) => item.id === transferId);
  if (!transfer) throw new Error(`transfer ${transferId} not found`);
  const history = (ensureHistories(todayMonth).get(transferId) ?? []).map((entry) => ({ ...entry }));
  return { transfer: { ...transfer }, history };
}

/**
 * POST /transfers/{id}/approve — 서버가 동의·한도·계좌 자격을 검사한 뒤 실행한다. 목은 실행 성공만 흉내 낸다.
 * 실행 중(APPROVED)인 건을 다시 승인하면 서버는 같은 기관거래고유번호로 재시도한다 — 목은 둘 다 성공으로 둔다.
 */
export function approveTransferMock(id: number, now: string): ApproveTransferDto {
  const target = (transfers ?? []).find((transfer) => transfer.id === id);
  transfers = (transfers ?? []).map((transfer) =>
    transfer.id === id ? { ...transfer, status: "EXECUTED", executedAt: now } : transfer
  );
  if (target !== undefined) {
    appendHistory(now.slice(0, 7).replace("-", ""), id, {
      action: "EXECUTE",
      basis: `금융망 H0000 — 기관거래고유번호 ${now.slice(0, 10).replaceAll("-", "")}00${id}, 금액 ${target.requiredAmount}, 계좌 ${target.fromAccountId}→${target.toAccountId}`,
      at: now,
    });
  }
  return { id, status: "EXECUTED", executedAt: now, failReason: null };
}

/** POST /transfers/{id}/postpone — 제안은 PROPOSED 로 남고 서버는 감사 로그(HOLD)만 남긴다 */
export function postponeTransferMock(id: number, now: string): void {
  const target = (transfers ?? []).find((transfer) => transfer.id === id);
  if (target === undefined) return;
  appendHistory(now.slice(0, 7).replace("-", ""), id, {
    action: "HOLD",
    basis: `사용자 보류(나중에) — 출금일 ${target.dueDate}, 제안액 ${target.requiredAmount}`,
    at: now,
  });
}

/** 테스트·개발 재시작용 */
export function resetTransferMocks(): void {
  transfers = null;
  histories = null;
}
