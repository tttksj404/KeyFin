import { ContractMismatchError } from "@/lib/contract";
import { maskAccount, maskCardNumber } from "@/lib/mask";
import { fromServerWon, type KRW } from "@/lib/money";

/**
 * 금융망 연결 계약 (docs/api-contract.md LINK, 2026-09-10 백엔드 자료).
 * 서버가 KeyFin 사용자 토큰으로 인증하고, 입력한 금융망 이메일로 회원을 조회해 userKey 를 서버에 보관한다.
 * userKey 는 응답에 없고 클라이언트가 보내지도 않는다.
 */
export type FinanceLinkRequest = { financeEmail: string };

/**
 * GET /links/status. 미연결도 정상 상태라 200 + false 로 온다.
 * 백엔드가 연결 응답과 같은 DTO 를 써서 필드가 connected 다 (Notion 의 financeConnected 는 미수정 오기, 2026-09-11 백엔드 확인)
 */
export type FinanceStatusDto = { connected: boolean };

export type FinanceLinkResponseDto = { connected: boolean };

/** 금융망 이메일 제한: 형식과 최대 100자 (COMMON_001 을 미리 막는다) */
export const FINANCE_EMAIL_MAX_LENGTH = 100;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function canSubmitFinanceEmail(email: string): boolean {
  const trimmed = email.trim();
  return EMAIL.test(trimmed) && trimmed.length <= FINANCE_EMAIL_MAX_LENGTH;
}

/**
 * GET /links/candidates 응답 DTO (docs/api-contract.md LINK, FR-USR-02, 2026-09-11 Swagger).
 * 조회할 때 서버가 금융망 목록을 KeyFin 에 동기화하므로 모든 항목에 KeyFin id 가 있다(계좌·카드는 id 공간이 따로다).
 * id 는 POST /links·연결 해제·수입 계좌 지정의 식별자이고, managed 는 관리 대상(연결됨) 여부다.
 */
export type LinkCandidateAccountDto = {
  id: number;
  finAccountNo: string;
  bankCode: string;
  bankName: string;
  balance: number;
  managed: boolean;
};

export type LinkCandidateCardDto = {
  id: number;
  cardNo: string;
  issuerName: string;
  cardName: string;
  withdrawalAccountNo: string;
  managed: boolean;
};

export type LinkCandidatesDto = { accounts: LinkCandidateAccountDto[]; cards: LinkCandidateCardDto[] };

/**
 * 화면 모델. 금액은 KRW 문자열로, 번호는 마스킹된 표시값으로 바꿔 둔다.
 * 원본 번호는 계좌·카드를 한 집합에서 고르는 선택 키로만 쓰고(id 는 계좌·카드끼리 겹친다) 화면에는 내보내지 않는다.
 */
export type LinkAccount = {
  id: number;
  finAccountNo: string;
  bankCode: string;
  bankName: string;
  maskedNo: string;
  balance: KRW;
  linked: boolean;
};

export type LinkCard = {
  id: number;
  cardNo: string;
  issuerName: string;
  cardName: string;
  maskedNo: string;
  maskedWithdrawalNo: string;
  linked: boolean;
};

export type LinkCandidates = { accounts: LinkAccount[]; cards: LinkCard[] };

/** POST /links — 후보의 KeyFin id 목록(각 최대 50개). 이미 관리 중인 항목은 서버가 건너뛴다(멱등) */
export type LinkRequest = { accountIds: number[]; cardIds: number[] };

/** 새로 연결된 수 */
export type LinkResponseDto = { accounts: number; cards: number };

function won(value: number, field: string): KRW {
  try {
    return fromServerWon(value);
  } catch {
    throw new ContractMismatchError(field);
  }
}

/** 서버 id 는 양의 정수(Long)다. POST /links 가 @Positive 로 검증한다 */
function keyFinId(value: number, field: string): number {
  if (!Number.isSafeInteger(value) || value <= 0) throw new ContractMismatchError(field);
  return value;
}

function toLinkAccount(dto: LinkCandidateAccountDto): LinkAccount {
  if (dto.finAccountNo.length === 0) throw new ContractMismatchError("accounts.finAccountNo");
  return {
    id: keyFinId(dto.id, "accounts.id"),
    finAccountNo: dto.finAccountNo,
    bankCode: dto.bankCode,
    bankName: dto.bankName,
    maskedNo: maskAccount(dto.finAccountNo),
    balance: won(dto.balance, "accounts.balance"),
    linked: dto.managed,
  };
}

function toLinkCard(dto: LinkCandidateCardDto): LinkCard {
  if (dto.cardNo.length === 0) throw new ContractMismatchError("cards.cardNo");
  return {
    id: keyFinId(dto.id, "cards.id"),
    cardNo: dto.cardNo,
    issuerName: dto.issuerName,
    cardName: dto.cardName,
    maskedNo: maskCardNumber(dto.cardNo),
    maskedWithdrawalNo: maskAccount(dto.withdrawalAccountNo),
    linked: dto.managed,
  };
}

export function toLinkCandidates(dto: LinkCandidatesDto): LinkCandidates {
  return { accounts: dto.accounts.map(toLinkAccount), cards: dto.cards.map(toLinkCard) };
}

/** 연결된 항목은 선택 대상이 아니다 (행이 '연결됨'으로 잠긴다) */
export function isLinkSelectable(item: { linked: boolean }): boolean {
  return !item.linked;
}

/** 체크 토글. 새 Set 을 돌려주어 호출부가 그대로 setState 에 넣을 수 있다 */
export function toggleLinkSelection(selected: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(selected);
  if (!next.delete(id)) next.add(id);
  return next;
}

/**
 * 선택 집합(계좌번호·카드번호)을 POST /links 본문(KeyFin id 목록)으로 바꾼다.
 * 후보 목록을 근거로 걸러내므로 이미 연결된 항목이나 사라진 후보는 요청에 섞이지 않는다.
 */
export function toLinkRequest(candidates: LinkCandidates, selected: ReadonlySet<string>): LinkRequest {
  return {
    accountIds: candidates.accounts.filter((a) => isLinkSelectable(a) && selected.has(a.finAccountNo)).map((a) => a.id),
    cardIds: candidates.cards.filter((c) => isLinkSelectable(c) && selected.has(c.cardNo)).map((c) => c.id),
  };
}

export function countLinkRequest(request: LinkRequest): number {
  return request.accountIds.length + request.cardIds.length;
}

/** 실제로 보낼 것이 하나라도 있어야 연결 요청을 한다 */
export function canSubmitLinks(request: LinkRequest): boolean {
  return countLinkRequest(request) > 0;
}

/**
 * 하단 버튼이 할 일. 새로 고른 항목이 있으면 연결하고, 없어도 이미 연결된 항목이 있으면 요청 없이 다음 단계로 간다.
 * 온보딩을 다시 시작한 사용자가 전부 연결해 둔 상태로 들어와도 막히지 않게 하려는 것이다.
 */
export type LinkCtaAction = "link" | "next" | "none";

export function linkCtaAction(candidates: LinkCandidates, request: LinkRequest): LinkCtaAction {
  if (canSubmitLinks(request)) return "link";
  const hasLinked = candidates.accounts.some((a) => a.linked) || candidates.cards.some((c) => c.linked);
  return hasLinked ? "next" : "none";
}

/** 후보가 아예 없으면 빈 상태 화면으로 간다 (시안 asset-select/empty) */
export function hasNoLinkCandidates(candidates: LinkCandidates): boolean {
  return candidates.accounts.length === 0 && candidates.cards.length === 0;
}

/** 헤더 '전체 선택'이 다룰 수 있는 항목. 이미 연결된 행은 잠겨 있어 뺀다 */
export function selectableLinkIds(candidates: LinkCandidates): string[] {
  return [
    ...candidates.accounts.filter(isLinkSelectable).map((account) => account.finAccountNo),
    ...candidates.cards.filter(isLinkSelectable).map((card) => card.cardNo),
  ];
}

/** 고를 수 있는 항목이 있고 그것을 전부 골랐을 때만 true. 전부 연결된 목록은 '전체 선택'이 의미 없다 */
export function areAllLinksSelected(candidates: LinkCandidates, selected: ReadonlySet<string>): boolean {
  const ids = selectableLinkIds(candidates);
  return ids.length > 0 && ids.every((id) => selected.has(id));
}

/** '전체 선택'을 누른 결과. 이미 전부 골랐으면 전부 푼다 */
export function toggleSelectAllLinks(candidates: LinkCandidates, selected: ReadonlySet<string>): Set<string> {
  const ids = selectableLinkIds(candidates);
  if (!areAllLinksSelected(candidates, selected)) return new Set([...selected, ...ids]);

  const next = new Set(selected);
  for (const id of ids) next.delete(id);
  return next;
}

/* ───────────── PAGE-32 연결 관리 (FR-USR-05) ───────────── */

export type LinkAssetKind = "account" | "card";

/** 연결 해제 요청 대상. 계좌·카드는 id 공간이 따로라 종류와 함께 다닌다 */
export type LinkAssetRef = { kind: LinkAssetKind; id: number };

/** 연결 관리 화면의 한 줄 */
export type LinkAssetItem = LinkAssetRef & {
  /** 목록 key. 계좌 1 과 카드 1 이 함께 있을 수 있다 */
  key: string;
  /** 계좌는 은행명, 카드는 카드 이름 */
  title: string;
  /** 로고를 찾을 은행·카드사 이름. 계좌는 bankCode 로 먼저 찾는다 */
  logoName: string;
  bankCode?: string;
  maskedNo: string;
  /** 수입 계좌 여부. 카드·연결하지 않은 계좌는 false, 계좌 목록(GET /accounts)을 아직 못 받았으면 null(모름) */
  isIncome: boolean | null;
};

export type LinkManagement = {
  linkedAccounts: LinkAssetItem[];
  linkedCards: LinkAssetItem[];
  /** 관리 대상이 아닌 계좌·카드(계좌 먼저). 해제한 항목도 여기로 돌아온다 */
  unlinked: LinkAssetItem[];
};

export function linkAssetKey({ kind, id }: LinkAssetRef): string {
  return `${kind}-${id}`;
}

function accountAssetItem(account: LinkAccount, incomeAccountId: number | null | undefined): LinkAssetItem {
  return {
    kind: "account",
    id: account.id,
    key: linkAssetKey({ kind: "account", id: account.id }),
    title: account.bankName,
    logoName: account.bankName,
    bankCode: account.bankCode,
    maskedNo: account.maskedNo,
    isIncome: !account.linked ? false : incomeAccountId === undefined ? null : account.id === incomeAccountId,
  };
}

function cardAssetItem(card: LinkCard): LinkAssetItem {
  return {
    kind: "card",
    id: card.id,
    key: linkAssetKey({ kind: "card", id: card.id }),
    title: card.cardName,
    logoName: card.issuerName,
    maskedNo: card.maskedNo,
    isIncome: false,
  };
}

/**
 * 후보 목록을 연결된 계좌·연결된 카드·연결하지 않은 자산으로 나눈다.
 * 수입 여부는 후보에 없어 GET /accounts 의 수입 계좌 id 로 채운다 — undefined 는 계좌 목록을 아직 모르는 것이다.
 * 해제하면 서버가 수입 지정도 풀므로 연결하지 않은 계좌는 수입 계좌일 수 없다.
 */
export function toLinkManagement(candidates: LinkCandidates, incomeAccountId: number | null | undefined): LinkManagement {
  const toAccount = (account: LinkAccount) => accountAssetItem(account, incomeAccountId);
  return {
    linkedAccounts: candidates.accounts.filter((account) => account.linked).map(toAccount),
    linkedCards: candidates.cards.filter((card) => card.linked).map(cardAssetItem),
    unlinked: [
      ...candidates.accounts.filter((account) => !account.linked).map(toAccount),
      ...candidates.cards.filter((card) => !card.linked).map(cardAssetItem),
    ],
  };
}

/** 연결 관리에서는 행마다 바로 연결한다 — 한 항목만 담은 POST /links 본문 */
export function linkRequestFor({ kind, id }: LinkAssetRef): LinkRequest {
  return kind === "account" ? { accountIds: [id], cardIds: [] } : { accountIds: [], cardIds: [id] };
}

/** 연결하지 않은 자산 목록은 계좌·카드가 섞여 종류를 번호 앞에 붙인다 */
export function linkAssetSubtitle(item: LinkAssetItem, withKind: boolean): string {
  if (!withKind) return item.maskedNo;
  return `${item.kind === "account" ? "계좌" : "카드"} · ${item.maskedNo}`;
}

export type UnlinkNotice = { title: string; description: string; incomeWarning: string | null };

const UNLINK_DESCRIPTION =
  "해제하면 새 거래를 더 이상 불러오지 않아요. 지금까지의 거래 이력은 그대로 남고, '연결하지 않은 자산'에서 다시 연결할 수 있어요.";
/** 관리 중인 수입 계좌가 없으면 서버가 결제 준비 이체 제안을 만들지 않는다 (TransferProposalService, 2026-09-17 코드 확인) */
const INCOME_CONSEQUENCE = "수입 계좌를 다시 지정할 때까지 결제 준비 이체 제안을 받을 수 없어요.";

/**
 * 해제 확인 창 문구 (Pencil gohga). 계좌 해제는 수입 계좌 지정도 푼다(Account.unlink).
 * 수입 여부를 모르면(계좌 목록 조회 전·실패) 경고를 빼지 않고 조건부로 알린다.
 */
export function unlinkNotice(item: LinkAssetItem): UnlinkNotice {
  const noun = item.kind === "account" ? "계좌" : "카드";
  const incomeWarning =
    item.kind === "card" || item.isIncome === false
      ? null
      : item.isIncome === true
        ? `수입 계좌 지정도 함께 풀려요. ${INCOME_CONSEQUENCE}`
        : `수입 계좌로 지정돼 있다면 지정도 함께 풀려요. ${INCOME_CONSEQUENCE}`;
  return { title: `${item.title} ${noun} 연결을 해제할까요?`, description: UNLINK_DESCRIPTION, incomeWarning };
}
