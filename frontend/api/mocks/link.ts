import { ApiError } from "@/api/error";
import type {
  FinanceLinkRequest,
  FinanceLinkResponseDto,
  FinanceStatusDto,
  LinkCandidateAccountDto,
  LinkCandidateCardDto,
  LinkCandidatesDto,
  LinkRequest,
  LinkResponseDto,
} from "@/features/link/model";

/**
 * 목 규칙: 금융망에 있는 이메일만 연결된다.
 * 서버 없이도 성공·없는 회원·중복 연결 세 경우를 모두 확인하려고 둔 값이다.
 */
export const MOCK_FINANCE_EMAIL = "finance@qwer.com";
/** 다른 KeyFin 계정이 이미 쓰고 있는 금융망 계정 (LINK_001) */
export const MOCK_TAKEN_FINANCE_EMAIL = "taken@qwer.com";

/** 앱이 도는 동안만 유지되는 연결 상태. 서버의 users.fin_user_key 자리를 대신한다 */
let connected = false;

export function financeStatusMock(): FinanceStatusDto {
  return { connected };
}

/** 온보딩을 마친 사용자로 시작할 때: 연결됨 + 후보 계좌·카드 전부 관리 대상 (리로드로 목이 초기화돼도 홈이 열리게) */
export function seedConnectedMock(): void {
  connected = true;
  for (const account of CANDIDATE_ACCOUNTS) managedAccounts.add(account.id);
  for (const card of CANDIDATE_CARDS) managedCards.add(card.id);
}

/** 테스트·개발 재시작용 */
export function resetLinkMocks(): void {
  connected = false;
  managedAccounts.clear();
  managedCards.clear();
}

export function connectFinanceMock({ financeEmail }: FinanceLinkRequest): FinanceLinkResponseDto {
  const email = financeEmail.trim().toLowerCase();
  if (email === MOCK_TAKEN_FINANCE_EMAIL) {
    throw new ApiError(409, "LINK_001", "해당 금융망 사용자는 이미 다른 계정과 연결되어 있습니다.");
  }
  if (email !== MOCK_FINANCE_EMAIL) {
    throw new ApiError(404, "FINANCE_001", "금융망에서 일치하는 사용자를 찾을 수 없습니다.");
  }
  connected = true;
  return { connected: true };
}

/**
 * 연결 후보 목록. 서버는 조회할 때 금융망 목록을 KeyFin 에 동기화해 id 를 붙인다 — 목은 고정 id 로 둔다(계좌·카드는 id 공간이 따로다).
 * 로고 있는 은행(088·004·090)과 로고 없는 폴백 타일(999)을 섞어 두 경우를 다 보이게 했다.
 * 서버처럼 처음에는 전부 미선택(managed=false)이고, 연결한 뒤 다시 들어오면 '연결됨'으로 잠긴다.
 */
const CANDIDATE_ACCOUNTS: readonly Omit<LinkCandidateAccountDto, "managed">[] = [
  { id: 1, finAccountNo: "0885401234567890", bankCode: "088", bankName: "신한은행", balance: 2_450_000 },
  { id: 2, finAccountNo: "0041202345678901", bankCode: "004", bankName: "국민은행", balance: 318_400 },
  { id: 3, finAccountNo: "0903303456789012", bankCode: "090", bankName: "카카오뱅크", balance: 1_007_250 },
  { id: 4, finAccountNo: "9990104567890123", bankCode: "999", bankName: "싸피은행", balance: 50_000 },
];

const CANDIDATE_CARDS: readonly Omit<LinkCandidateCardDto, "managed">[] = [
  { id: 1, cardNo: "5310123412341234", issuerName: "신한카드", cardName: "Deep Dream 체크", withdrawalAccountNo: "0885401234567890" },
  { id: 2, cardNo: "9410432143214321", issuerName: "국민카드", cardName: "노리 체크", withdrawalAccountNo: "0041202345678901" },
];

/** 앱이 도는 동안만 유지되는 관리 대상(is_managed=true) id. 서버의 accounts·cards 테이블 자리를 대신한다 */
const managedAccounts = new Set<number>();
const managedCards = new Set<number>();

export function linkCandidatesMock(): LinkCandidatesDto {
  return {
    accounts: CANDIDATE_ACCOUNTS.map((a) => ({ ...a, managed: managedAccounts.has(a.id) })),
    cards: CANDIDATE_CARDS.map((c) => ({ ...c, managed: managedCards.has(c.id) })),
  };
}

/** 계좌 목(GET /accounts)이 쓰는 관리 중 계좌. 연결 목(POST /links)과 같은 상태를 봐서 연결한 계좌가 곧바로 나온다 */
export function managedAccountsMock(): Omit<LinkCandidateAccountDto, "managed">[] {
  return CANDIDATE_ACCOUNTS.filter((account) => managedAccounts.has(account.id));
}

/** 새로 관리 대상이 된 수를 돌려준다. 이미 관리 중인 id 는 세지 않는다(멱등) */
function manageAll(ids: readonly number[], managed: Set<number>): number {
  let added = 0;
  for (const id of ids) {
    if (managed.has(id)) continue;
    managed.add(id);
    added += 1;
  }
  return added;
}

/** 응답은 '새로 연결된 수' 다 */
export function createLinksMock({ accountIds, cardIds }: LinkRequest): LinkResponseDto {
  return { accounts: manageAll(accountIds, managedAccounts), cards: manageAll(cardIds, managedCards) };
}

/**
 * DELETE /links/accounts/{id}. 서버처럼 본인 계좌인지만 보고 관리 대상에서 뺀다 — 이미 해제된 계좌도 성공(멱등).
 * 수입 계좌 지정 해제는 계좌 목(releaseIncomeAccountMock)이 맡는다(계좌 목이 이 파일을 읽어 순환을 피한다).
 */
export function unlinkAccountMock(accountId: number): void {
  if (!CANDIDATE_ACCOUNTS.some((account) => account.id === accountId)) {
    throw new ApiError(404, "LINK_004", "계좌를 찾을 수 없습니다. 후보 목록을 다시 조회해 주세요.");
  }
  managedAccounts.delete(accountId);
}

/** DELETE /links/cards/{id}. 본인 카드인지만 보고 관리 대상에서 뺀다(멱등) */
export function unlinkCardMock(cardId: number): void {
  if (!CANDIDATE_CARDS.some((card) => card.id === cardId)) {
    throw new ApiError(404, "LINK_005", "카드를 찾을 수 없습니다. 후보 목록을 다시 조회해 주세요.");
  }
  managedCards.delete(cardId);
}
