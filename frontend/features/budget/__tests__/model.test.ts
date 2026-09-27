import {
  budgetConfirmedMock,
  budgetProposalMock,
  budgetProposedMock,
  confirmBudgetMock,
  createProposalMock,
  currentBudgetMock,
  resetBudgetMocks,
  updateEmergencyFundMock,
} from "@/api/mocks/budget";
import { envelopeShortName } from "@/features/budget/catalog";
import { ApiError } from "@/api/error";
import {
  emergencyAmountError,
  isEmergencyDirty,
  toEmergencyFund,
  toEmergencyFundRequest,
  toEmergencyInput,
  WARNING_REMAINING_RATE,
  budgetHealth,
  budgetPeriodLabel,
  budgetPeriodShortLabel,
  hasSpendingHistory,
  isWithinPeriod,
  monthlyAvgPercent,
  parseEnvelopeId,
  proposalBasisKind,
  sortByMonthlyAvg,
  envelopeHealth,
  sumAmounts,
  toBudget,
  toBudgetProposal,
  toConfirmRequest,
  toProposalRows,
  usedBarPercent,
  usedPercent,
} from "@/features/budget/model";
import { ContractMismatchError } from "@/lib/contract";

const TODAY = "2026-09-08";
const MONTH = "202609";

describe("envelopeHealth · usedPercent · envelopeShortName", () => {
  it("봉투별 상태는 잔액·잔여율로 정하고 승인 전은 unset 이다", () => {
    const { envelopes } = toBudget(budgetConfirmedMock(TODAY));
    expect(envelopes.map(envelopeHealth)).toEqual(["good", "good", "good", "warning", "over", "good", "good"]);
    expect(toBudget(budgetProposedMock(TODAY)).envelopes.map(envelopeHealth)).toEqual(Array(7).fill("unset"));
  });

  it("확정액 0 인 봉투는 잔여율이 null 이라 빈 막대이고, 쓴 돈이 있으면 over, 없으면 good 이다", () => {
    const withSpent = toBudget(budgetConfirmedMock(TODAY, { 3: 0 })).envelopes[2];
    expect(withSpent).toMatchObject({ confirmed: "0", spent: "4000", remaining: "-4000", remainingRate: null });
    expect(envelopeHealth(withSpent)).toBe("over");
    expect(usedBarPercent(withSpent.remainingRate)).toBe(0);
    expect(envelopeHealth({ ...withSpent, spent: "0", remaining: "0" })).toBe("good");
  });

  it("사용률은 100 − 잔여율이고 초과면 100 을 넘으며, 막대는 100 에서 자른다", () => {
    expect(usedPercent(36)).toBe(64);
    expect(usedPercent(-9)).toBe(109);
    expect(usedPercent(130)).toBe(0);
    expect(usedBarPercent(-9)).toBe(100);
    expect(usedBarPercent(null)).toBe(0);
  });

  it("차트 축 이름은 카탈로그의 짧은 이름을 쓰고 모르는 id 는 서버 이름이다", () => {
    expect(envelopeShortName(6, "편의점·마트·잡화")).toBe("마트");
    expect(envelopeShortName(99, "새 봉투")).toBe("새 봉투");
  });
});

describe("toBudget (GET /budgets/current)", () => {
  it("확정 주기는 금액을 KRW 로 바꾸고, 봉투 제안액은 null 이며 잔여율은 서버 값 그대로다", () => {
    const budget = toBudget(budgetConfirmedMock(TODAY));
    expect(budget).toMatchObject({
      budgetId: 1,
      month: MONTH,
      periodFrom: "2026-09-01",
      periodTo: "2026-09-30",
      status: "CONFIRMED",
      isConfirmed: true,
    });
    expect(budget.total).toEqual({ confirmed: "500000", spent: "320000", remaining: "180000", remainingRate: 36 });
    expect(budget.envelopes[4]).toEqual({
      envelopeId: 5,
      name: "쇼핑",
      proposed: null,
      confirmed: "90000",
      spent: "98000",
      remaining: "-8000",
      remainingRate: -9,
    });
  });

  it("확정 전 주기는 total 이 null 이고 봉투에는 제안액만 있다", () => {
    const budget = toBudget(budgetProposedMock(TODAY));
    expect(budget.status).toBe("PROPOSED");
    expect(budget.isConfirmed).toBe(false);
    expect(budget.total).toBeNull();
    expect(budget.envelopes[0]).toMatchObject({ proposed: "100000", confirmed: null, spent: null, remaining: null, remainingRate: null });
  });

  it("모르는 status 는 UNKNOWN 으로 흡수한다", () => {
    expect(toBudget({ ...budgetProposedMock(TODAY), status: "ARCHIVED" }).status).toBe("UNKNOWN");
  });

  it("CONFIRMED 인데 total 이 없거나, PROPOSED 인데 제안액이 없으면 계약 불일치다", () => {
    expect(() => toBudget({ ...budgetConfirmedMock(TODAY), total: null })).toThrow(ContractMismatchError);
    const proposed = budgetProposedMock(TODAY);
    expect(() => toBudget({ ...proposed, envelopes: [{ ...proposed.envelopes[0], proposedAmount: null }] })).toThrow(ContractMismatchError);
  });

  it("비상금 풀을 함께 옮긴다 — amount 0 은 미설정이고 넘겨 쓰면 remaining 이 음수다", () => {
    const dto = budgetConfirmedMock(TODAY);

    expect(toBudget(dto).emergency).toEqual({ amount: "0", spent: "0", remaining: "0" });
    expect(toBudget({ ...dto, emergency: { amount: 200000, spent: 230000, remaining: -30000 } }).emergency).toEqual({
      amount: "200000",
      spent: "230000",
      remaining: "-30000",
    });
  });

  it("금액·잔여율이 정수가 아니거나 월·기간·budgetId 형식이 틀리면 계약 불일치다", () => {
    const dto = budgetConfirmedMock(TODAY);
    const total = dto.total ?? { confirmed: 0, spent: 0, remaining: 0, remainingRate: null };
    expect(() => toBudget({ ...dto, total: { ...total, spent: 320000.5 } })).toThrow(ContractMismatchError);
    expect(() => toBudget({ ...dto, total: { ...total, remainingRate: 36.4 } })).toThrow(ContractMismatchError);
    expect(() => toBudget({ ...dto, month: "2026-09" })).toThrow(ContractMismatchError);
    expect(() => toBudget({ ...dto, periodFrom: "20260901" })).toThrow(ContractMismatchError);
    expect(() => toBudget({ ...dto, periodTo: "2026-08-31" })).toThrow(ContractMismatchError);
    expect(() => toBudget({ ...dto, budgetId: 0 })).toThrow(ContractMismatchError);
  });
});

describe("budgetPeriodLabel · budgetPeriodShortLabel · isWithinPeriod", () => {
  it("같은 달이면 끝 날짜만, 달이 넘어가면 달까지 쓴다 — 주기 라벨(month)로 'N월' 이라 쓰지 않는다", () => {
    expect(budgetPeriodLabel({ periodFrom: "2026-09-01", periodTo: "2026-09-30" })).toBe("9월 1일~30일");
    expect(budgetPeriodLabel({ periodFrom: "2026-08-23", periodTo: "2026-09-22" })).toBe("8월 23일~9월 22일");
    expect(budgetPeriodShortLabel({ periodFrom: "2026-08-23", periodTo: "2026-09-22" })).toBe("8.23~9.22");
  });

  it("거래일이 주기 시작일~마지막 날(포함) 안인지 가른다", () => {
    const period = { periodFrom: "2026-08-23", periodTo: "2026-09-22" };
    expect(isWithinPeriod(period, "2026-08-23")).toBe(true);
    expect(isWithinPeriod(period, "2026-09-22")).toBe(true);
    expect(isWithinPeriod(period, "2026-08-22")).toBe(false);
    expect(isWithinPeriod(period, "2026-09-23")).toBe(false);
  });
});

describe("proposalBasisKind · toProposalRows (예산 확정 화면)", () => {
  const budget = toBudget(budgetProposedMock(TODAY));
  const analysis = toBudgetProposal(budgetProposalMock(MONTH));

  it("같은 예산의 분석 결과가 있으면 history/template, 없거나 다른 예산 것이면 unknown 이다", () => {
    expect(proposalBasisKind(budget, analysis)).toBe("history");
    const templateDto = budgetProposalMock(MONTH);
    const template = toBudgetProposal({ ...templateDto, envelopes: templateDto.envelopes.map((e) => ({ ...e, monthlyAvg: 0 })) });
    expect(proposalBasisKind(budget, template)).toBe("template");
    expect(proposalBasisKind(budget, undefined)).toBe("unknown");
    expect(proposalBasisKind(budget, { ...analysis, budgetId: 99 })).toBe("unknown");
  });

  it("금액은 현재 주기 제안액, 월평균은 같은 예산의 분석 결과가 있을 때만 붙인다", () => {
    expect(toProposalRows(budget, analysis)[0]).toEqual({ envelopeId: 1, name: "외식", proposed: "100000", monthlyAvg: "112000" });
    expect(toProposalRows(budget, undefined)[0]).toEqual({ envelopeId: 1, name: "외식", proposed: "100000", monthlyAvg: null });
  });
});

describe("예산 목 — 서버 동작 흉내 (제안 1회 · 조회 시 지연 생성 · 확정 1회)", () => {
  beforeEach(resetBudgetMocks);

  it("조회는 예산이 없으면 제안을 만들어 PROPOSED 로 주고, 그 뒤 제안 생성은 409 BUDGET_001 이다", () => {
    expect(currentBudgetMock(TODAY).status).toBe("PROPOSED");
    expect(() => createProposalMock(MONTH)).toThrow("해당 월의 예산이 이미 존재합니다.");
  });

  it("확정하면 조회가 CONFIRMED 와 확정 금액을 주고, 두 번째 확정은 409 BUDGET_003 이다", () => {
    createProposalMock(MONTH);
    const entries = [1, 2, 3, 4, 5, 6, 7].map((envelopeId) => ({ envelopeId, amount: envelopeId === 1 ? "120000" : "50000" }));
    const request = toConfirmRequest(entries);
    expect(confirmBudgetMock(1, request, TODAY)).toEqual({ budgetId: 1, month: MONTH, status: "CONFIRMED" });
    const confirmed = toBudget(currentBudgetMock(TODAY));
    expect(confirmed.status).toBe("CONFIRMED");
    expect(confirmed.envelopes[0].confirmed).toBe("120000");
    expect(() => confirmBudgetMock(1, request, TODAY)).toThrow("이미 확정된 예산은 변경할 수 없습니다.");
  });
});

describe("toBudgetProposal · sumAmounts · toConfirmRequest", () => {
  it("제안은 제안액과 근거 월평균을 KRW 문자열로 바꾼다", () => {
    const proposal = toBudgetProposal(budgetProposalMock(MONTH));
    expect(proposal.month).toBe(MONTH);
    expect(proposal.status).toBe("PROPOSED");
    expect(proposal.basis).toBe("최근 3개월 평균");
    expect(proposal.envelopes).toHaveLength(7);
    expect(proposal.envelopes[0]).toEqual({ envelopeId: 1, name: "외식", proposed: "100000", monthlyAvg: "112000" });
  });

  it("제안 합계는 500,000 이고 월평균 합계가 더 크다", () => {
    const { envelopes } = toBudgetProposal(budgetProposalMock(MONTH));
    expect(sumAmounts(envelopes.map((envelope) => envelope.proposed))).toBe("500000");
    expect(sumAmounts(envelopes.map((envelope) => envelope.monthlyAvg))).toBe("533000");
    expect(sumAmounts([])).toBe("0");
  });

  it("month·budgetId·금액이 계약과 다르면 계약 불일치다", () => {
    const dto = budgetProposalMock(MONTH);
    expect(() => toBudgetProposal({ ...dto, month: "2026-09" })).toThrow(ContractMismatchError);
    expect(() => toBudgetProposal({ ...dto, budgetId: 1.5 })).toThrow(ContractMismatchError);
    expect(() => toBudgetProposal({ ...dto, envelopes: [{ ...dto.envelopes[0], monthlyAvg: 92000.5 }] })).toThrow(
      ContractMismatchError
    );
  });

  it("승인 요청은 KRW 문자열을 원 정수로 되돌린다", () => {
    expect(toConfirmRequest([{ envelopeId: 1, amount: "120000" }])).toEqual({
      envelopes: [{ envelopeId: 1, amount: 120000 }],
    });
  });
});

describe("budgetHealth", () => {
  const base = { confirmed: "500000", spent: "320000" };

  it("남은 예산이 음수면 over, 잔여율이 30% 미만이면 warning, 나머지는 good", () => {
    expect(budgetHealth({ ...base, remaining: "180000", remainingRate: 36 })).toBe("good");
    expect(budgetHealth({ ...base, remaining: "100000", remainingRate: WARNING_REMAINING_RATE })).toBe("good");
    expect(budgetHealth({ ...base, remaining: "50000", remainingRate: WARNING_REMAINING_RATE - 1 })).toBe("warning");
    expect(budgetHealth({ ...base, remaining: "-1000", remainingRate: 0 })).toBe("over");
  });
});

describe("hasSpendingHistory · sortByMonthlyAvg · monthlyAvgPercent", () => {
  it("월평균이 하나라도 있으면 분석한 제안이고, 전부 0 이면 기본 템플릿 제안이다", () => {
    const dto = budgetProposalMock(MONTH);
    expect(hasSpendingHistory(toBudgetProposal(dto))).toBe(true);
    const template = { ...dto, basis: "기본 템플릿", envelopes: dto.envelopes.map((e) => ({ ...e, monthlyAvg: 0 })) };
    expect(hasSpendingHistory(toBudgetProposal(template))).toBe(false);
  });

  it("월평균이 큰 순으로 줄 세우고, 같으면 원래 봉투 순서를 지킨다", () => {
    const envelopes = [
      { envelopeId: 1, name: "외식", proposed: "0", monthlyAvg: "50000" },
      { envelopeId: 2, name: "교통비", proposed: "0", monthlyAvg: "90000" },
      { envelopeId: 3, name: "기타", proposed: "0", monthlyAvg: "50000" },
    ];
    expect(sortByMonthlyAvg(envelopes).map((e) => e.envelopeId)).toEqual([2, 1, 3]);
    expect(envelopes.map((e) => e.envelopeId)).toEqual([1, 2, 3]);
  });

  it("막대 길이는 가장 큰 값을 100 으로 본 정수 비율이고, 최댓값이 0 이면 0 이다", () => {
    expect(monthlyAvgPercent("120650", "120650")).toBe(100);
    expect(monthlyAvgPercent("84300", "120650")).toBe(69);
    expect(monthlyAvgPercent("0", "0")).toBe(0);
  });
});

describe("parseEnvelopeId", () => {
  it("양의 정수만 봉투 id 로 받고 배열이면 첫 값을 쓴다", () => {
    expect(parseEnvelopeId("1")).toBe(1);
    expect(parseEnvelopeId(["7", "2"])).toBe(7);
    expect(parseEnvelopeId("0")).toBeNull();
    expect(parseEnvelopeId("2.5")).toBeNull();
    expect(parseEnvelopeId("외식")).toBeNull();
    expect(parseEnvelopeId(undefined)).toBeNull();
  });
});

describe("비상금 (PUT /budgets/{budgetId}/emergency)", () => {
  const emergency = { amount: 200000, spent: 45000, remaining: 155000 };

  it("계약 예시를 화면 모델로 바꾸고 예산 id 를 검증한다", () => {
    expect(toEmergencyFund({ budgetId: 11, emergency })).toEqual({
      budgetId: 11,
      emergency: { amount: "200000", spent: "45000", remaining: "155000" },
    });
    expect(() => toEmergencyFund({ budgetId: 0, emergency })).toThrow(ContractMismatchError);
  });

  it("남은 금액은 음수로도 온다(비상금을 넘겨 썼을 때)", () => {
    const over = toEmergencyFund({ budgetId: 11, emergency: { amount: 100000, spent: 130000, remaining: -30000 } });
    expect(over.emergency.remaining).toBe("-30000");
  });

  it("0 이상 1,000원 단위만 보낼 수 있고 빈 칸은 해제(0)로 본다", () => {
    expect(emergencyAmountError("")).toBeNull();
    expect(emergencyAmountError("200000")).toBeNull();
    expect(emergencyAmountError("200500")).not.toBeNull();

    expect(toEmergencyFundRequest("")).toEqual({ amount: 0 });
    expect(toEmergencyFundRequest("200000")).toEqual({ amount: 200000 });
    expect(() => toEmergencyFundRequest("200500")).toThrow();
  });

  it("미설정은 빈 칸으로 두고, 같은 금액이면 저장하지 않는다", () => {
    const unset = { amount: "0", spent: "0", remaining: "0" } as const;
    const set = { amount: "200000", spent: "45000", remaining: "155000" } as const;

    expect(toEmergencyInput(unset)).toBe("");
    expect(toEmergencyInput(set)).toBe("200000");
    expect(isEmergencyDirty("", unset)).toBe(false);
    expect(isEmergencyDirty("200000", set)).toBe(false);
    expect(isEmergencyDirty("300000", set)).toBe(true);
    expect(isEmergencyDirty("", set)).toBe(true);
  });

  it("목에 저장한 비상금은 현재 주기 예산 조회에도 그대로 나온다", () => {
    resetBudgetMocks();
    expect(toBudget(currentBudgetMock()).emergency.amount).toBe("0");

    const saved = updateEmergencyFundMock(toBudget(currentBudgetMock()).budgetId, { amount: 200000 });
    expect(saved.emergency).toEqual({ amount: 200000, spent: 0, remaining: 200000 });
    expect(toBudget(currentBudgetMock()).emergency.amount).toBe("200000");

    const codeOf = (run: () => void) => {
      try {
        run();
        return null;
      } catch (error) {
        return error instanceof ApiError ? error.code : "NOT_API_ERROR";
      }
    };
    expect(codeOf(() => updateEmergencyFundMock(1, { amount: 200500 }))).toBe("BUDGET_005");
    expect(codeOf(() => updateEmergencyFundMock(1, { amount: -1000 }))).toBe("COMMON_001");
    expect(codeOf(() => updateEmergencyFundMock(999, { amount: 1000 }))).toBe("BUDGET_002");
    resetBudgetMocks();
  });
});
