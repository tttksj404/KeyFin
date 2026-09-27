import { accountListMock, resetAccountMocks, setIncomeAccountMock } from "@/api/mocks/account";
import { createLinksMock, linkCandidatesMock, resetLinkMocks } from "@/api/mocks/link";
import {
  balanceAsOfLabel,
  canSubmitIncomeAccount,
  incomeAccountIdOf,
  linkedCards,
  totalBalance,
  toAccountSummary,
  toLinkedAccounts,
  type AccountSummaryDto,
} from "@/features/account/model";
import { toLinkCandidates } from "@/features/link/model";
import { ContractMismatchError } from "@/lib/contract";


const accountDto: AccountSummaryDto = {
  accountId: "acc_001",
  bankName: "하네스은행",
  alias: "생활비 통장",
  accountNumber: "110-123-456789",
  balance: "3469520",
};

describe("toAccountSummary", () => {
  it("계좌번호를 마스킹하고 잔액은 문자열 그대로 보관한다", () => {
    const summary = toAccountSummary(accountDto);
    expect(summary.maskedAccountNumber).toBe("110-***-**6789");
    expect(summary.balance).toBe("3469520");
    expect(summary.alias).toBe("생활비 통장");
  });

  it("잔액이 정수 문자열이 아니면 계약 불일치 오류를 던진다", () => {
    expect(() => toAccountSummary({ ...accountDto, balance: "3469520.50" })).toThrow(ContractMismatchError);
  });
});

describe("toLinkedAccounts · incomeAccountIdOf · totalBalance (GET /accounts)", () => {
  beforeEach(() => {
    resetLinkMocks();
    resetAccountMocks();
  });

  it("관리 중인 계좌를 KeyFin id·마스킹 번호·KRW 잔액으로 바꾸고, 총 자산은 잔액 합계다", () => {
    createLinksMock({ accountIds: [1, 2], cardIds: [] });
    const accounts = toLinkedAccounts(accountListMock());
    expect(accounts.map((account) => account.accountId)).toEqual([1, 2]);
    expect(accounts[0]).toMatchObject({ bankName: "신한은행", maskedNo: "088*********7890", balance: "2450000", alias: null });
    expect(totalBalance(accounts)).toBe("2768400");
  });

  it("연결 계좌가 없으면 빈 목록이고 총 자산은 0 원이다", () => {
    const accounts = toLinkedAccounts(accountListMock());
    expect(accounts).toEqual([]);
    expect(totalBalance(accounts)).toBe("0");
  });

  it("isManaged=false 가 섞여 와도 목록에 두지 않는다", () => {
    createLinksMock({ accountIds: [1, 2], cardIds: [] });
    const dto = accountListMock();
    dto.items[1] = { ...dto.items[1], isManaged: false };
    expect(toLinkedAccounts(dto).map((account) => account.accountId)).toEqual([1]);
  });

  it("수입 계좌는 사용자당 1개이고, 새로 지정하면 이전 것이 풀린다", () => {
    createLinksMock({ accountIds: [1, 3], cardIds: [] });
    expect(incomeAccountIdOf(toLinkedAccounts(accountListMock()))).toBeNull();
    setIncomeAccountMock(3);
    expect(incomeAccountIdOf(toLinkedAccounts(accountListMock()))).toBe(3);
    setIncomeAccountMock(1);
    const accounts = toLinkedAccounts(accountListMock());
    expect(accounts.filter((account) => account.isIncome).map((account) => account.accountId)).toEqual([1]);
  });

  it("관리 중이 아닌 계좌를 수입 계좌로 지정하면 ACCOUNT_001 로 거절한다", () => {
    expect(() => setIncomeAccountMock(4)).toThrow("계좌를 찾을 수 없습니다.");
  });

  it("잔액이 정수가 아니거나 갱신 시각 형식이 틀리면 계약 불일치로 막는다", () => {
    createLinksMock({ accountIds: [1], cardIds: [] });
    const dto = accountListMock();
    expect(() => toLinkedAccounts({ items: [{ ...dto.items[0], balance: 100.5 }] })).toThrow(ContractMismatchError);
    expect(() => toLinkedAccounts({ items: [{ ...dto.items[0], balanceUpdatedAt: "2026-09-11" }] })).toThrow(ContractMismatchError);
  });
});

describe("canSubmitIncomeAccount", () => {
  beforeEach(() => {
    resetLinkMocks();
    resetAccountMocks();
  });

  it("목록에 있는 계좌를 골랐을 때만 지정할 수 있다", () => {
    createLinksMock({ accountIds: [3], cardIds: [] });
    const accounts = toLinkedAccounts(accountListMock());
    expect(canSubmitIncomeAccount(accounts, null)).toBe(false);
    expect(canSubmitIncomeAccount(accounts, 999)).toBe(false);
    expect(canSubmitIncomeAccount(accounts, 3)).toBe(true);
  });
});

describe("linkedCards (카드는 아직 금융망 후보에서)", () => {
  beforeEach(resetLinkMocks);

  it("연결된 카드만 KeyFin id 를 달고 나온다", () => {
    createLinksMock({ accountIds: [], cardIds: [2] });
    expect(linkedCards(toLinkCandidates(linkCandidatesMock()))).toEqual([expect.objectContaining({ cardId: 2, cardName: "노리 체크" })]);
  });
});

describe("balanceAsOfLabel", () => {
  beforeEach(() => {
    resetLinkMocks();
    resetAccountMocks();
  });

  it("계좌마다 갱신 시각이 다르면 가장 오래된 시각을 기준으로 쓴다", () => {
    createLinksMock({ accountIds: [1, 2], cardIds: [] });
    const dto = accountListMock();
    dto.items[0] = { ...dto.items[0], balanceUpdatedAt: "2026-09-11T09:05:00" };
    dto.items[1] = { ...dto.items[1], balanceUpdatedAt: "2026-09-11T14:30:00.500" };
    expect(balanceAsOfLabel(toLinkedAccounts(dto))).toBe("9월 11일 (금) 09:05 기준");
  });

  it("계좌가 없으면 문구도 없다", () => {
    expect(balanceAsOfLabel([])).toBeNull();
  });
});
