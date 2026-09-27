import { ApiError } from "@/api/error";
import { accountListMock, releaseIncomeAccountMock, resetAccountMocks, setIncomeAccountMock } from "@/api/mocks/account";
import { ContractMismatchError } from "@/lib/contract";
import {
  connectFinanceMock,
  createLinksMock,
  financeStatusMock,
  linkCandidatesMock,
  MOCK_FINANCE_EMAIL,
  MOCK_TAKEN_FINANCE_EMAIL,
  resetLinkMocks,
  unlinkAccountMock,
  unlinkCardMock,
} from "@/api/mocks/link";
import { incomeAccountIdOf, toLinkedAccounts } from "@/features/account/model";
import { financeErrorMessage, isRetryableFinanceError, unlinkErrorMessage } from "@/features/link/errors";
import {
  areAllLinksSelected,
  canSubmitFinanceEmail,
  canSubmitLinks,
  countLinkRequest,
  linkAssetSubtitle,
  linkCtaAction,
  linkRequestFor,
  FINANCE_EMAIL_MAX_LENGTH,
  hasNoLinkCandidates,
  isLinkSelectable,
  selectableLinkIds,
  toggleLinkSelection,
  toggleSelectAllLinks,
  toLinkCandidates,
  toLinkManagement,
  toLinkRequest,
  unlinkNotice,
} from "@/features/link/model";

beforeEach(resetLinkMocks);

describe("canSubmitFinanceEmail", () => {
  it("이메일 형식이고 100자 이하여야 보낼 수 있다", () => {
    expect(canSubmitFinanceEmail(MOCK_FINANCE_EMAIL)).toBe(true);
    expect(canSubmitFinanceEmail("  finance@qwer.com  ")).toBe(true);
    expect(canSubmitFinanceEmail("finance@qwer")).toBe(false);
    expect(canSubmitFinanceEmail("")).toBe(false);
  });

  it("100자를 넘으면 서버 COMMON_001 전에 막는다", () => {
    const long = `${"a".repeat(FINANCE_EMAIL_MAX_LENGTH)}@qwer.com`;
    expect(long.length).toBeGreaterThan(FINANCE_EMAIL_MAX_LENGTH);
    expect(canSubmitFinanceEmail(long)).toBe(false);
  });
});

describe("connectFinanceMock", () => {
  it("금융망에 있는 이메일이면 연결된다", () => {
    expect(connectFinanceMock({ financeEmail: MOCK_FINANCE_EMAIL })).toEqual({ connected: true });
  });

  it("없는 회원은 FINANCE_001, 이미 연결된 계정은 LINK_001 이다", () => {
    expect(() => connectFinanceMock({ financeEmail: "nobody@qwer.com" })).toThrow(ApiError);
    try {
      connectFinanceMock({ financeEmail: "nobody@qwer.com" });
    } catch (error) {
      expect((error as ApiError).code).toBe("FINANCE_001");
    }
    try {
      connectFinanceMock({ financeEmail: MOCK_TAKEN_FINANCE_EMAIL });
    } catch (error) {
      expect((error as ApiError).code).toBe("LINK_001");
      expect((error as ApiError).status).toBe(409);
    }
  });
});

describe("financeErrorMessage · isRetryableFinanceError", () => {
  it("확인된 code 는 정해진 문구를 쓰고 모르는 code 는 서버 message 를 쓴다", () => {
    expect(financeErrorMessage(new ApiError(409, "LINK_001", "무시됨"))).toContain("다른 KeyFin 계정");
    expect(financeErrorMessage(new ApiError(500, "COMMON_006", "서버 내부 오류가 발생했습니다."))).toBe(
      "서버 내부 오류가 발생했습니다."
    );
  });

  it("이미 연결됐거나 없는 회원은 다시 눌러도 소용없다", () => {
    expect(isRetryableFinanceError(new ApiError(404, "FINANCE_001", ""))).toBe(false);
    expect(isRetryableFinanceError(new ApiError(409, "LINK_001", ""))).toBe(false);
    expect(isRetryableFinanceError(new ApiError(503, "FINANCE_004", ""))).toBe(true);
  });
});

describe("financeStatusMock", () => {
  it("연결 전에는 false, 연결에 성공하면 true 다", () => {
    expect(financeStatusMock()).toEqual({ connected: false });
    connectFinanceMock({ financeEmail: MOCK_FINANCE_EMAIL });
    expect(financeStatusMock()).toEqual({ connected: true });
  });

  it("연결에 실패하면 상태는 그대로 false 다", () => {
    expect(() => connectFinanceMock({ financeEmail: MOCK_TAKEN_FINANCE_EMAIL })).toThrow();
    expect(financeStatusMock()).toEqual({ connected: false });
  });
});

describe("toLinkCandidates", () => {
  it("계좌번호·카드번호를 마스킹하고 잔액을 KRW 로 바꾼다", () => {
    const candidates = toLinkCandidates(linkCandidatesMock());
    const shinhan = candidates.accounts[0];
    expect(shinhan.finAccountNo).toBe("0885401234567890");
    expect(shinhan.maskedNo).toBe("088*********7890");
    expect(shinhan.balance).toBe("2450000");
    expect(candidates.cards[0].maskedNo).toBe("5310********1234");
  });

  it("출금 계좌번호도 마스킹해 둔다", () => {
    const card = toLinkCandidates(linkCandidatesMock()).cards[0];
    expect(card.maskedWithdrawalNo).toBe("088*********7890");
  });

  it("잔액이 정수가 아니면 계약 불일치로 막는다", () => {
    const dto = linkCandidatesMock();
    dto.accounts[0].balance = 1234.5;
    expect(() => toLinkCandidates(dto)).toThrow(ContractMismatchError);
  });

  it("계좌번호가 비어 있으면 계약 불일치로 막는다", () => {
    const dto = linkCandidatesMock();
    dto.accounts[0].finAccountNo = "";
    expect(() => toLinkCandidates(dto)).toThrow(ContractMismatchError);
  });

  it("처음에는 전부 미선택이고, 연결 여부와 무관하게 KeyFin id 를 들고 있다", () => {
    const { accounts, cards } = toLinkCandidates(linkCandidatesMock());
    expect([...accounts, ...cards].some((item) => item.linked)).toBe(false);
    expect(accounts.map((a) => a.id)).toEqual([1, 2, 3, 4]);
    expect(cards.map((c) => c.id)).toEqual([1, 2]);
  });

  it("managed 를 linked 로 옮긴다", () => {
    createLinksMock({ accountIds: [3], cardIds: [] });
    const { accounts } = toLinkCandidates(linkCandidatesMock());
    expect(accounts.filter((a) => a.linked)).toEqual([expect.objectContaining({ id: 3, bankName: "카카오뱅크" })]);
  });

  it("id 가 양의 정수가 아니면 계약 불일치로 막는다", () => {
    const dto = linkCandidatesMock();
    dto.cards[0].id = 0;
    expect(() => toLinkCandidates(dto)).toThrow(ContractMismatchError);
  });
});

describe("toggleLinkSelection", () => {
  it("없으면 넣고 있으면 뺀다", () => {
    const once = toggleLinkSelection(new Set(), "a");
    expect([...once]).toEqual(["a"]);
    expect([...toggleLinkSelection(once, "a")]).toEqual([]);
  });

  it("원본을 바꾸지 않는다", () => {
    const before = new Set(["a"]);
    toggleLinkSelection(before, "b");
    expect([...before]).toEqual(["a"]);
  });
});

describe("toLinkRequest · canSubmitLinks", () => {
  it("선택한 계좌·카드를 KeyFin id 목록으로 나눠 담는다", () => {
    const candidates = toLinkCandidates(linkCandidatesMock());
    const request = toLinkRequest(candidates, new Set(["0885401234567890", "5310123412341234"]));
    expect(request).toEqual({ accountIds: [1], cardIds: [1] });
    expect(countLinkRequest(request)).toBe(2);
    expect(canSubmitLinks(request)).toBe(true);
  });

  it("이미 연결된 항목은 골라도 요청에 넣지 않는다", () => {
    createLinksMock({ accountIds: [3], cardIds: [] });
    const candidates = toLinkCandidates(linkCandidatesMock());
    const linked = candidates.accounts.find((a) => a.linked);
    expect(linked).toBeDefined();
    const request = toLinkRequest(candidates, new Set([linked!.finAccountNo]));
    expect(request).toEqual({ accountIds: [], cardIds: [] });
    expect(canSubmitLinks(request)).toBe(false);
  });

  it("후보에 없는 번호는 무시한다", () => {
    const request = toLinkRequest(toLinkCandidates(linkCandidatesMock()), new Set(["없는번호"]));
    expect(canSubmitLinks(request)).toBe(false);
  });
});

describe("isLinkSelectable · hasNoLinkCandidates", () => {
  it("연결된 항목은 고를 수 없다", () => {
    expect(isLinkSelectable({ linked: false })).toBe(true);
    expect(isLinkSelectable({ linked: true })).toBe(false);
  });

  it("계좌·카드가 모두 없을 때만 빈 상태다", () => {
    expect(hasNoLinkCandidates(toLinkCandidates(linkCandidatesMock()))).toBe(false);
    expect(hasNoLinkCandidates({ accounts: [], cards: [] })).toBe(true);
  });
});

describe("createLinksMock", () => {
  it("새로 연결된 수만 센다 — 다시 보내도 0 이다(멱등)", () => {
    const request = { accountIds: [1], cardIds: [1] };
    expect(createLinksMock(request)).toEqual({ accounts: 1, cards: 1 });
    expect(createLinksMock(request)).toEqual({ accounts: 0, cards: 0 });
  });

  it("연결한 항목은 후보 목록에서 managed 로 바뀐다", () => {
    createLinksMock({ accountIds: [2], cardIds: [] });
    const account = linkCandidatesMock().accounts.find((a) => a.finAccountNo === "0041202345678901");
    expect(account?.managed).toBe(true);
  });
});

describe("selectableLinkIds · areAllLinksSelected · toggleSelectAllLinks", () => {
  it("전체 선택은 이미 연결된 항목을 빼고 고른다", () => {
    createLinksMock({ accountIds: [3], cardIds: [] });
    const candidates = toLinkCandidates(linkCandidatesMock());
    const linked = candidates.accounts.find((account) => account.linked);
    expect(linked).toBeDefined();

    const ids = selectableLinkIds(candidates);
    expect(ids).not.toContain(linked!.finAccountNo);
    expect(ids).toHaveLength(candidates.accounts.length + candidates.cards.length - 1);

    const selected = toggleSelectAllLinks(candidates, new Set());
    expect(areAllLinksSelected(candidates, selected)).toBe(true);
    const request = toLinkRequest(candidates, selected);
    expect(request.accountIds).toHaveLength(candidates.accounts.length - 1);
    expect(request.cardIds).toHaveLength(candidates.cards.length);
  });

  it("일부만 고른 상태에서 누르면 나머지가 채워진다", () => {
    const candidates = toLinkCandidates(linkCandidatesMock());
    const partial = new Set([selectableLinkIds(candidates)[0]]);
    expect(areAllLinksSelected(candidates, partial)).toBe(false);
    expect(areAllLinksSelected(candidates, toggleSelectAllLinks(candidates, partial))).toBe(true);
  });

  it("전부 고른 상태에서 다시 누르면 전부 푼다", () => {
    const candidates = toLinkCandidates(linkCandidatesMock());
    const all = toggleSelectAllLinks(candidates, new Set());
    expect(toggleSelectAllLinks(candidates, all).size).toBe(0);
  });

  it("고를 수 있는 항목이 없으면 전체 선택된 상태로 보지 않는다", () => {
    expect(areAllLinksSelected({ accounts: [], cards: [] }, new Set())).toBe(false);
  });
});

describe("linkCtaAction", () => {
  it("연결된 것도 고른 것도 없으면 누를 수 없다", () => {
    const candidates = toLinkCandidates(linkCandidatesMock());
    expect(linkCtaAction(candidates, toLinkRequest(candidates, new Set()))).toBe("none");
  });

  it("새로 고른 항목이 있으면 연결한다", () => {
    const candidates = toLinkCandidates(linkCandidatesMock());
    expect(linkCtaAction(candidates, toLinkRequest(candidates, new Set(["0885401234567890"])))).toBe("link");
  });

  it("이미 연결된 항목이 있고 새로 고른 게 없으면 그대로 다음 단계로 간다", () => {
    createLinksMock({ accountIds: [], cardIds: [2] });
    const candidates = toLinkCandidates(linkCandidatesMock());
    expect(linkCtaAction(candidates, toLinkRequest(candidates, new Set()))).toBe("next");
  });

  it("이미 연결된 항목이 있어도 새로 고르면 연결이 먼저다", () => {
    createLinksMock({ accountIds: [3], cardIds: [] });
    const candidates = toLinkCandidates(linkCandidatesMock());
    expect(linkCtaAction(candidates, toLinkRequest(candidates, new Set(["5310123412341234"])))).toBe("link");
  });
});

describe("toLinkManagement (PAGE-32 연결 관리)", () => {
  it("연결된 계좌·연결된 카드·연결하지 않은 자산(계좌 먼저)으로 나눈다", () => {
    createLinksMock({ accountIds: [1, 2], cardIds: [2] });
    const { linkedAccounts, linkedCards, unlinked } = toLinkManagement(toLinkCandidates(linkCandidatesMock()), null);
    expect(linkedAccounts.map((item) => item.key)).toEqual(["account-1", "account-2"]);
    expect(linkedCards.map((item) => item.key)).toEqual(["card-2"]);
    expect(unlinked.map((item) => item.key)).toEqual(["account-3", "account-4", "card-1"]);
  });

  it("계좌 1 과 카드 1 처럼 id 가 겹쳐도 key 는 다르다", () => {
    const { unlinked } = toLinkManagement(toLinkCandidates(linkCandidatesMock()), null);
    const keys = unlinked.map((item) => item.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("수입 뱃지는 계좌 목록의 수입 계좌로 채우고, 목록을 모르면 null 이다", () => {
    createLinksMock({ accountIds: [1, 2], cardIds: [1] });
    const candidates = toLinkCandidates(linkCandidatesMock());
    expect(toLinkManagement(candidates, 2).linkedAccounts.map((item) => item.isIncome)).toEqual([false, true]);
    expect(toLinkManagement(candidates, undefined).linkedAccounts.map((item) => item.isIncome)).toEqual([null, null]);
    expect(toLinkManagement(candidates, undefined).linkedCards[0].isIncome).toBe(false);
  });

  it("연결하지 않은 계좌는 수입 계좌일 수 없다", () => {
    const { unlinked } = toLinkManagement(toLinkCandidates(linkCandidatesMock()), 3);
    expect(unlinked.find((item) => item.key === "account-3")?.isIncome).toBe(false);
  });

  it("카드는 카드 이름을 제목으로, 카드사를 로고 이름으로 쓴다", () => {
    const card = toLinkManagement(toLinkCandidates(linkCandidatesMock()), null).unlinked.find((item) => item.kind === "card");
    expect(card).toEqual(expect.objectContaining({ title: "Deep Dream 체크", logoName: "신한카드" }));
    expect(card?.bankCode).toBeUndefined();
  });
});

describe("linkRequestFor · linkAssetSubtitle", () => {
  it("행 하나만 담은 POST /links 본문을 만든다", () => {
    expect(linkRequestFor({ kind: "account", id: 3 })).toEqual({ accountIds: [3], cardIds: [] });
    expect(linkRequestFor({ kind: "card", id: 1 })).toEqual({ accountIds: [], cardIds: [1] });
  });

  it("계좌·카드가 섞인 목록에서만 종류를 붙인다", () => {
    const [account] = toLinkManagement(toLinkCandidates(linkCandidatesMock()), null).unlinked;
    expect(linkAssetSubtitle(account, false)).toBe(account.maskedNo);
    expect(linkAssetSubtitle(account, true)).toBe(`계좌 · ${account.maskedNo}`);
  });
});

describe("unlinkNotice (해제 확인 창)", () => {
  const managedItems = (incomeAccountId: number | null | undefined) => {
    createLinksMock({ accountIds: [1, 2], cardIds: [1] });
    return toLinkManagement(toLinkCandidates(linkCandidatesMock()), incomeAccountId);
  };

  it("수입 계좌면 지정 해제와 이체 제안 중단을 경고한다", () => {
    const [income] = managedItems(1).linkedAccounts;
    const notice = unlinkNotice(income);
    expect(notice.title).toBe("신한은행 계좌 연결을 해제할까요?");
    expect(notice.incomeWarning).toBe(
      "수입 계좌 지정도 함께 풀려요. 수입 계좌를 다시 지정할 때까지 결제 준비 이체 제안을 받을 수 없어요."
    );
  });

  it("수입 계좌가 아니거나 카드면 경고가 없다", () => {
    const { linkedAccounts, linkedCards } = managedItems(1);
    expect(unlinkNotice(linkedAccounts[1]).incomeWarning).toBeNull();
    expect(unlinkNotice(linkedCards[0])).toEqual(
      expect.objectContaining({ title: "Deep Dream 체크 카드 연결을 해제할까요?", incomeWarning: null })
    );
  });

  it("수입 여부를 모르면 경고를 빼지 않고 조건부로 알린다", () => {
    const [account] = managedItems(undefined).linkedAccounts;
    expect(unlinkNotice(account).incomeWarning).toMatch(/^수입 계좌로 지정돼 있다면/);
  });
});

describe("연결 해제 목 (DELETE /links/accounts|cards/{id})", () => {
  beforeEach(resetAccountMocks);

  it("관리 대상에서 빼고, 이미 해제된 항목을 다시 해제해도 성공한다(멱등)", () => {
    createLinksMock({ accountIds: [1], cardIds: [1] });
    unlinkAccountMock(1);
    unlinkCardMock(1);
    expect(() => unlinkAccountMock(1)).not.toThrow();
    const candidates = toLinkCandidates(linkCandidatesMock());
    expect(candidates.accounts[0].linked).toBe(false);
    expect(candidates.cards[0].linked).toBe(false);
  });

  it("없는 계좌는 LINK_004, 없는 카드는 LINK_005 다", () => {
    expect(() => unlinkAccountMock(999)).toThrow(expect.objectContaining({ status: 404, code: "LINK_004" }));
    expect(() => unlinkCardMock(999)).toThrow(expect.objectContaining({ status: 404, code: "LINK_005" }));
  });

  it("수입 계좌를 해제하면 다시 연결해도 수입 지정은 돌아오지 않는다", () => {
    createLinksMock({ accountIds: [1, 2], cardIds: [] });
    setIncomeAccountMock(1);
    unlinkAccountMock(1);
    releaseIncomeAccountMock(1);
    createLinksMock({ accountIds: [1], cardIds: [] });
    expect(incomeAccountIdOf(toLinkedAccounts(accountListMock()))).toBeNull();
  });

  it("다른 계좌를 해제하면 수입 지정은 그대로다", () => {
    createLinksMock({ accountIds: [1, 2], cardIds: [] });
    setIncomeAccountMock(1);
    releaseIncomeAccountMock(2);
    expect(incomeAccountIdOf(toLinkedAccounts(accountListMock()))).toBe(1);
  });
});

describe("unlinkErrorMessage", () => {
  it("404 는 선택 화면과 달리 다시 고르라고 하지 않는다", () => {
    expect(unlinkErrorMessage(new ApiError(404, "LINK_004", "계좌를 찾을 수 없습니다."))).toBe(
      "이미 목록에서 사라진 계좌예요. 목록을 새로 불러왔어요."
    );
    expect(unlinkErrorMessage(new ApiError(404, "LINK_005", "카드를 찾을 수 없습니다."))).toBe(
      "이미 목록에서 사라진 카드예요. 목록을 새로 불러왔어요."
    );
  });

  it("모르는 코드는 서버 문구, 네트워크 오류는 기본 문구", () => {
    expect(unlinkErrorMessage(new ApiError(500, "COMMON_006", "서버 오류"))).toBe("서버 오류");
    expect(unlinkErrorMessage(new Error("network"))).toBe("연결을 해제하지 못했어요. 잠시 후 다시 시도해 주세요.");
  });
});
