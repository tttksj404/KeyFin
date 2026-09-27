import type { LinkCandidates, LinkCard } from "@/features/link/model";
import { ContractMismatchError } from "@/lib/contract";
import { formatMonthDay, formatTime, KST_LOCAL_DATE_TIME, parseKSTLocalDateTime } from "@/lib/date";
import { addKRW, fromServerWon, isKRW, type KRW } from "@/lib/money";
import { maskAccount } from "@/lib/mask";

export type AccountSummaryDto = {
  accountId: string;
  bankName: string;
  alias: string;
  accountNumber: string;
  balance: string;
};

export type AccountSummary = {
  accountId: string;
  bankName: string;
  alias: string;
  maskedAccountNumber: string;
  balance: KRW;
};

export function toAccountSummary(dto: AccountSummaryDto): AccountSummary {
  if (!isKRW(dto.balance)) throw new ContractMismatchError("balance");
  return {
    accountId: dto.accountId,
    bankName: dto.bankName,
    alias: dto.alias,
    maskedAccountNumber: maskAccount(dto.accountNumber),
    balance: dto.balance,
  };
}

/**
 * GET /accounts 응답 (docs/api-contract.md ACCOUNT, 2026-09-11 백엔드 develop 코드 확인).
 * 관리 중(isManaged=true)인 계좌만 id 오름차순으로 온다. 은행 코드는 없어 로고는 은행명으로 찾는다.
 * balance 는 금융망 실시간 값이 아니라 마지막으로 갱신된 스냅샷이고 balanceUpdatedAt 은 시간대 없는 KST 다.
 */
export type AccountItemDto = {
  id: number;
  finAccountNo: string;
  bankName: string;
  alias: string | null;
  isIncome: boolean;
  isManaged: boolean;
  balance: number;
  /** "YYYY-MM-DDTHH:mm:ss" (KST) */
  balanceUpdatedAt: string;
};

export type AccountListDto = { items: AccountItemDto[] };

/** 연결된(관리 중) 계좌. id 가 PUT /accounts/{id}/income·거래 필터(accountId)의 KeyFin 계좌 id 다 */
export type LinkedAccount = {
  accountId: number;
  bankName: string;
  alias: string | null;
  maskedNo: string;
  balance: KRW;
  isIncome: boolean;
  /** "YYYY-MM-DDTHH:mm:ss" (KST). 표시할 때 lib/date 로 읽는다 */
  balanceUpdatedAt: string;
};

function toLinkedAccount(dto: AccountItemDto): LinkedAccount {
  if (!Number.isSafeInteger(dto.id) || dto.id <= 0) throw new ContractMismatchError("items.id");
  if (dto.finAccountNo.length === 0) throw new ContractMismatchError("items.finAccountNo");
  if (!KST_LOCAL_DATE_TIME.test(dto.balanceUpdatedAt)) throw new ContractMismatchError("items.balanceUpdatedAt");
  let balance: KRW;
  try {
    balance = fromServerWon(dto.balance);
  } catch {
    throw new ContractMismatchError("items.balance");
  }
  return {
    accountId: dto.id,
    bankName: dto.bankName,
    alias: dto.alias,
    maskedNo: maskAccount(dto.finAccountNo),
    balance,
    isIncome: dto.isIncome,
    balanceUpdatedAt: dto.balanceUpdatedAt,
  };
}

/** 관리 중인 계좌만 남긴다. 서버가 이미 거르지만 isManaged=false 가 섞여 와도 목록에 두지 않는다 */
export function toLinkedAccounts(dto: AccountListDto): LinkedAccount[] {
  return dto.items.filter((item) => item.isManaged).map(toLinkedAccount);
}

/**
 * "내 총 자산" 아래 기준 시각 문구. 잔액은 계좌마다 따로 갱신된 스냅샷이라, 가장 오래된 갱신 시각을 기준으로 보여 준다
 * (그 뒤의 변동은 반영되지 않았을 수 있다는 뜻이 되도록). 계좌가 없으면 null.
 */
export function balanceAsOfLabel(accounts: readonly LinkedAccount[]): string | null {
  if (accounts.length === 0) return null;
  const oldest = accounts
    .map((account) => parseKSTLocalDateTime(account.balanceUpdatedAt))
    .reduce((min, date) => (date.getTime() < min.getTime() ? date : min));
  return `${formatMonthDay(oldest)} ${formatTime(oldest)} 기준`;
}

/** 지금 수입 계좌로 지정된 계좌 id. 사용자당 1개이고 없으면 null 이다 */
export function incomeAccountIdOf(accounts: readonly LinkedAccount[]): number | null {
  return accounts.find((account) => account.isIncome)?.accountId ?? null;
}

/** 수입 계좌 지정(PAGE-05) 선택지 = 연결된 계좌 */
export type IncomeAccountOption = LinkedAccount;

/**
 * 연결된 카드. 카드 목록 API 가 아직 없어 금융망 후보 중 managed 카드로 만든다.
 * 후보의 id 가 KeyFin 카드 id 라 거래 필터(cardId)에 그대로 쓴다 (docs/api-contract.md LINK).
 */
export type LinkedCard = Pick<LinkCard, "issuerName" | "cardName" | "maskedNo"> & { cardId: number };

export function linkedCards(candidates: LinkCandidates): LinkedCard[] {
  return candidates.cards
    .filter((card) => card.linked)
    .map(({ id, issuerName, cardName, maskedNo }) => ({ cardId: id, issuerName, cardName, maskedNo }));
}

/** 자산 탭 "내 총 자산" = 연결 계좌 잔액 합계. 카드는 잔액이 없어 뺀다. 잔액은 서버가 마지막으로 갱신한 스냅샷이다 */
export function totalBalance(accounts: readonly LinkedAccount[]): KRW {
  return accounts.length === 0 ? "0" : addKRW(...accounts.map((account) => account.balance));
}

/** 지금 목록에 있는 계좌를 골랐을 때만 지정할 수 있다. 목록을 다시 받아 사라진 계좌는 무효다 */
export function canSubmitIncomeAccount(options: readonly IncomeAccountOption[], selectedId: number | null): boolean {
  return selectedId !== null && options.some((option) => option.accountId === selectedId);
}
