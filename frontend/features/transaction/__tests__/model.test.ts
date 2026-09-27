import { ApiError } from "@/api/error";
import {
  classifyTransactionMock,
  classifyTransactionsBulkMock,
  pendingTransactionsMock,
  resetTransactionMocks,
  subcategoriesMock,
  transactionListMock,
} from "@/api/mocks/transaction";
import {
  BULK_CLASSIFY_MAX,
  confirmStatusLabel,
  dutchAmountError,
  isIncoming,
  merchantLabel,
  monthFilterLabel,
  parseTransactionFilter,
  parseTransactionId,
  reclassifyBlockedReason,
  resolvePendingFocus,
  suggestedForBulk,
  toBulkClassifyResult,
  toClassifyResult,
  toDutchRequest,
  toFocusTransactionId,
  toSuggestedBulkRequest,
  toPendingTransactions,
  toSubcategories,
  toTransaction,
  toTransactionPage,
  transactionBadge,
  transactionCategoryLabel,
  transactionDateTimeLabel,
  txTypeLabel,
} from "@/features/transaction/model";
import { ContractMismatchError } from "@/lib/contract";
import { shiftMonthKey } from "@/lib/date";

describe("toTransaction", () => {
  const dto = pendingTransactionsMock().items[0];

  it("금액을 KRW 로, 거래일에서 월 키를 만들고 열거형을 유니온으로 옮긴다", () => {
    const tx = toTransaction(dto);
    expect(tx.amount).toBe("4500");
    expect(tx.monthKey).toBe("202609");
    expect(tx.txType).toBe("CARD");
    expect(tx.confirmStatus).toBe("PENDING");
    expect(tx.excludeTag).toBe("NONE");
    expect(tx.status).toBe("NORMAL");
    expect(tx.memo).toBeNull();
  });

  it("모르는 열거형 값은 UNKNOWN 으로 흡수하고 거래일 형식이 틀리면 계약 불일치다", () => {
    expect(toTransaction({ ...dto, txType: "COUPON", excludeTag: "GIFT" })).toMatchObject({ txType: "UNKNOWN", excludeTag: "UNKNOWN" });
    expect(() => toTransaction({ ...dto, txDate: "20260908" })).toThrow(ContractMismatchError);
    expect(() => toTransaction({ ...dto, amount: 4500.5 })).toThrow(ContractMismatchError);
  });
});

describe("pending · subcategories · classify", () => {
  it("미확정 목록은 커서·size 로 잘리고 마지막 쪽은 nextCursor 가 null 이다", () => {
    const first = pendingTransactionsMock(null, 1);
    expect(first.items.map((item) => item.id)).toEqual([501]);
    expect(first.nextCursor).toBe(501);

    const second = pendingTransactionsMock(first.nextCursor, 1);
    expect(second.items.map((item) => item.id)).toEqual([502]);
    expect(second.nextCursor).toBeNull();
  });

  it("미확정 목록과 세분류 22종을 변환한다", () => {
    expect(toPendingTransactions(pendingTransactionsMock()).items.map((item) => item.id)).toEqual([501, 502]);
    expect(toSubcategories(subcategoriesMock)).toHaveLength(22);
    expect(toSubcategories(subcategoriesMock)[1]).toEqual({ id: 102, name: "카페", envelopeId: 1, envelopeName: "외식" });
  });

  it("세분류는 봉투별로 묶여 오고(백엔드 SubcategoryListResponse) 화면 목록으로 펴진다", () => {
    const flattened = toSubcategories({
      items: [
        { envelopeId: 1, envelopeName: "외식", subcategories: [{ id: 101, name: "음식점" }, { id: 102, name: "카페" }] },
        { envelopeId: 7, envelopeName: "기타", subcategories: [{ id: 701, name: "교육" }] },
      ],
    });

    expect(flattened).toEqual([
      { id: 101, name: "음식점", envelopeId: 1, envelopeName: "외식" },
      { id: 102, name: "카페", envelopeId: 1, envelopeName: "외식" },
      { id: 701, name: "교육", envelopeId: 7, envelopeName: "기타" },
    ]);
    expect(toSubcategories({ items: [{ envelopeId: 3, envelopeName: "의료·건강", subcategories: [] }] })).toEqual([]);
  });

  it("확정 응답(develop 2026-09-15 모양)을 화면 모델로 바꾸고 더치페이 부담액은 KRW 로 바꾼다", () => {
    expect(toClassifyResult({ transactionId: 501, subcategoryId: 102, excludeTag: "NONE", adjustedAmount: null, confirmStatus: "CONFIRMED" })).toEqual({
      confirmStatus: "CONFIRMED",
      subcategoryId: 102,
      excludeTag: "NONE",
      adjustedAmount: null,
    });
    expect(toClassifyResult({ transactionId: 501, subcategoryId: null, excludeTag: "DUTCH", adjustedAmount: 15000, confirmStatus: "CONFIRMED" })).toMatchObject({
      excludeTag: "DUTCH",
      adjustedAmount: "15000",
    });
    expect(() =>
      toClassifyResult({ transactionId: 501, subcategoryId: null, excludeTag: "DUTCH", adjustedAmount: 1.5, confirmStatus: "CONFIRMED" })
    ).toThrow(ContractMismatchError);
  });

  it("미확정 거래는 봉투·세분류가 null 로 올 수 있고 화면은 미분류로 적는다", () => {
    const [pending] = toPendingTransactions({
      items: [
        {
          id: 9,
          txType: "CARD",
          merchantName: null,
          amount: 4500,
          txDate: "2026-09-08",
          txTime: "14:21:00",
          envelopeId: null,
          subcategoryId: null,
          subcategoryName: null,
          confirmStatus: "PENDING",
          excludeTag: "NONE",
          status: "NORMAL",
          memo: null,
          accountId: null,
          cardId: 7,
          adjustedAmount: null,
        },
      ],
      nextCursor: null,
    }).items;

    expect(pending).toMatchObject({ envelopeId: null, subcategoryId: null, subcategoryName: null, merchantName: null, cardId: 7, adjustedAmount: null });
    expect(transactionCategoryLabel(pending)).toBe("미분류");
    expect(merchantLabel(pending)).toBe("이름 없는 거래");
  });

  it("더치페이 부담액은 비거나 0이면 안 되고 결제 금액을 넘을 수 없다", () => {
    expect(dutchAmountError("", "12000")).toContain("입력");
    expect(dutchAmountError("0", "12000")).toContain("입력");
    expect(dutchAmountError("12001", "12000")).toContain("넘을 수 없어요");
    expect(dutchAmountError("12000", "12000")).toBeNull();
    expect(toDutchRequest("6000")).toEqual({ excludeTag: "DUTCH", adjustedAmount: 6000 });
  });

  it("목 확정은 미확정 목록에서 그 거래를 뺀다", () => {
    classifyTransactionMock(502, { excludeTag: "DUTCH", adjustedAmount: 6000 });
    expect(pendingTransactionsMock().items.map((item) => item.id)).toEqual([501]);
  });
});

describe("거래 목록 표시 (isIncoming · transactionCategoryLabel · transactionBadge)", () => {
  const base = toTransaction(pendingTransactionsMock().items[0]);

  it("입금만 들어온 돈이고 분류 자리에 '입금' 이라고 쓴다", () => {
    expect(isIncoming(base)).toBe(false);
    expect(transactionCategoryLabel(base)).toBe("카페");
    const deposit = { ...base, txType: "DEPOSIT" as const };
    expect(isIncoming(deposit)).toBe(true);
    expect(transactionCategoryLabel(deposit)).toBe("입금");
  });

  it("취소가 제외 태그보다 먼저이고, 태그가 없으면 뱃지도 없다", () => {
    expect(transactionBadge(base)).toBeNull();
    expect(transactionBadge({ ...base, excludeTag: "DUTCH" })).toBe("더치페이");
    expect(transactionBadge({ ...base, status: "CANCELED", excludeTag: "DUTCH" })).toBe("취소");
  });
});

describe("shiftMonthKey · monthFilterLabel", () => {
  it("해를 넘겨 달을 옮기고 라벨을 만든다", () => {
    expect(shiftMonthKey("202601", -1)).toBe("202512");
    expect(shiftMonthKey("202612", 1)).toBe("202701");
    expect(monthFilterLabel("202609")).toBe("2026년 9월");
  });
});

describe("parseTransactionFilter", () => {
  const THIS_MONTH = "202609";

  it("달이 없거나 틀리거나 미래면 이번 달로 돌린다", () => {
    expect(parseTransactionFilter({}, THIS_MONTH)).toEqual({ month: THIS_MONTH });
    expect(parseTransactionFilter({ month: "2026-08" }, THIS_MONTH)).toEqual({ month: THIS_MONTH });
    expect(parseTransactionFilter({ month: "202610" }, THIS_MONTH)).toEqual({ month: THIS_MONTH });
    expect(parseTransactionFilter({ month: "202608" }, THIS_MONTH)).toEqual({ month: "202608" });
  });

  it("id 는 양의 정수만 받고, 계좌와 카드가 둘 다 오면 계좌만 쓴다", () => {
    expect(parseTransactionFilter({ envelopeId: "3", accountId: "1", cardId: "2" }, THIS_MONTH)).toEqual({
      month: THIS_MONTH,
      envelopeId: 3,
      accountId: 1,
    });
    expect(parseTransactionFilter({ envelopeId: "0", cardId: ["2", "9"] }, THIS_MONTH)).toEqual({ month: THIS_MONTH, cardId: 2 });
  });
});

describe("transactionListMock · toTransactionPage", () => {
  const TODAY = "2026-09-20";

  it("20건씩 끊고 마지막 id 를 커서로 이어 받으면 겹치지 않는다", () => {
    const first = toTransactionPage(transactionListMock({ month: "202609" }, TODAY));
    expect(first.items).toHaveLength(20);
    expect(first.nextCursor).toBe(first.items[19].id);
    const second = toTransactionPage(transactionListMock({ month: "202609", cursor: first.nextCursor ?? undefined }, TODAY));
    expect(second.items.some((tx) => first.items.some((seen) => seen.id === tx.id))).toBe(false);
  });

  it("마지막 쪽은 nextCursor 가 null 이고 미래 달은 비어 있다", () => {
    const all = transactionListMock({ month: "202609", size: 100 }, TODAY);
    expect(all.nextCursor).toBeNull();
    expect(transactionListMock({ month: "202610" }, TODAY).items).toEqual([]);
  });

  it("봉투·카드 필터에 맞는 거래만 준다", () => {
    const envelope = transactionListMock({ month: "202609", envelopeId: 2, size: 100 }, TODAY);
    expect(envelope.items.every((tx) => tx.envelopeId === 2)).toBe(true);
    const account = transactionListMock({ month: "202609", accountId: 1, size: 100 }, TODAY);
    expect(account.items.some((tx) => tx.txType === "DEPOSIT")).toBe(true);
    expect(account.items.every((tx) => tx.txType !== "CARD")).toBe(true);
  });
});

describe("거래 상세 표시 (txTypeLabel · confirmStatusLabel · transactionDateTimeLabel · reclassifyBlockedReason)", () => {
  const card = toTransaction(pendingTransactionsMock().items[0]);

  it("거래 종류와 분류 상태를 화면 문구로 바꾸고 모르는 상태는 자리를 비운다", () => {
    expect(txTypeLabel(card)).toBe("카드 결제");
    expect(txTypeLabel(toTransaction({ ...pendingTransactionsMock().items[0], txType: "CARD_BILL" }))).toBe("카드대금");
    expect(txTypeLabel({ ...card, txType: "UNKNOWN" })).toBe("기타");
    expect(confirmStatusLabel(card)).toBe("확인 필요");
    expect(confirmStatusLabel({ ...card, confirmStatus: "AUTO" })).toBe("자동 분류");
    expect(confirmStatusLabel({ ...card, confirmStatus: "UNKNOWN" })).toBeNull();
  });

  it("날짜와 시각을 합쳐 KST 로 읽고 시각 형식이 틀리면 날짜만 쓴다", () => {
    expect(transactionDateTimeLabel(card)).toBe("2026.09.08 14:21");
    expect(transactionDateTimeLabel({ ...card, txTime: "" })).toBe("2026.09.08");
  });

  it("입금과 취소된 결제는 분류를 바꿀 수 없다", () => {
    expect(reclassifyBlockedReason(card)).toBeNull();
    expect(reclassifyBlockedReason({ ...card, txType: "DEPOSIT" })).toContain("입금");
    expect(reclassifyBlockedReason({ ...card, status: "CANCELED" })).toContain("취소");
  });
});

describe("알림에서 온 거래 찾기 (resolvePendingFocus · toFocusTransactionId)", () => {
  const items = toPendingTransactions(pendingTransactionsMock()).items;

  it("받은 목록에 있으면 그 거래를 돌려준다 — 분류 창을 바로 연다", () => {
    const focus = resolvePendingFocus(items, 502, true);
    expect(focus.state).toBe("found");
    expect(focus.state === "found" ? focus.transaction.id : null).toBe(502);
  });

  it("받은 쪽에 없고 더 받을 쪽이 있으면 계속 찾는다", () => {
    expect(resolvePendingFocus(items, 9999, true)).toEqual({ state: "searching" });
  });

  it("끝까지 받았는데 없으면 이미 정리한 거래다", () => {
    expect(resolvePendingFocus(items, 9999, false)).toEqual({ state: "gone" });
    expect(resolvePendingFocus([], 501, false)).toEqual({ state: "gone" });
  });

  it("라우트 파라미터는 양의 정수 모양일 때만 거래 id 로 본다", () => {
    expect(toFocusTransactionId("501")).toBe(501);
    expect(toFocusTransactionId("0")).toBeNull();
    expect(toFocusTransactionId("-3")).toBeNull();
    expect(toFocusTransactionId("12abc")).toBeNull();
    expect(toFocusTransactionId("../my/settings")).toBeNull();
    expect(toFocusTransactionId("99999999999999999999")).toBeNull();
    expect(toFocusTransactionId(undefined)).toBeNull();
    expect(toFocusTransactionId(["501"])).toBeNull();
  });
});

describe("parseTransactionId", () => {
  it("양의 정수만 거래 id 로 받고 배열이면 첫 값을 쓴다", () => {
    expect(parseTransactionId("501")).toBe(501);
    expect(parseTransactionId(["502", "503"])).toBe(502);
    expect(parseTransactionId("0")).toBeNull();
    expect(parseTransactionId("12.5")).toBeNull();
    expect(parseTransactionId("abc")).toBeNull();
    expect(parseTransactionId(undefined)).toBeNull();
  });
});

describe("목 확정과 거래 목록", () => {
  const TODAY = "2026-09-20";

  it("확정한 거래는 목록에서도 바뀐 봉투·세분류·상태로 나온다", () => {
    const target = transactionListMock({ month: "202609" }, TODAY).items[1];
    classifyTransactionMock(target.id, { subcategoryId: 201 });

    const after = transactionListMock({ month: "202609", size: 100 }, TODAY).items.find((item) => item.id === target.id);
    expect(after).toMatchObject({ envelopeId: 2, subcategoryId: 201, subcategoryName: "대중교통", confirmStatus: "CONFIRMED" });
    resetTransactionMocks();
  });
});

describe("일괄 확정 (PUT /transactions/classifications)", () => {
  it("응답의 건수는 0 이상 정수여야 한다", () => {
    expect(toBulkClassifyResult({ confirmed: 2, pendingRemain: 0 })).toEqual({ confirmed: 2, pendingRemain: 0 });
    expect(() => toBulkClassifyResult({ confirmed: -1, pendingRemain: 0 })).toThrow(ContractMismatchError);
    expect(() => toBulkClassifyResult({ confirmed: 1, pendingRemain: 1.5 })).toThrow(ContractMismatchError);
  });

  it("제안 세분류가 없는 거래는 한 번에 확정할 수 없어 빠진다", () => {
    resetTransactionMocks();
    const pending = toPendingTransactions(pendingTransactionsMock()).items;
    const withoutSuggestion = pending.map((transaction) => ({ ...transaction, subcategoryId: null }));

    expect(suggestedForBulk(pending).length).toBe(pending.filter((item) => item.subcategoryId !== null).length);
    expect(suggestedForBulk(withoutSuggestion)).toEqual([]);
    expect(toSuggestedBulkRequest(withoutSuggestion)).toEqual({ items: [] });
    resetTransactionMocks();
  });

  it("요청은 거래 id 와 제안 세분류만 담고 100건에서 자른다", () => {
    const many = Array.from({ length: BULK_CLASSIFY_MAX + 5 }, (_, index) => ({
      ...toPendingTransactions(pendingTransactionsMock()).items[0],
      id: index + 1,
      subcategoryId: 102,
    }));

    const request = toSuggestedBulkRequest(many);
    expect(request.items.length).toBe(BULK_CLASSIFY_MAX);
    expect(request.items[0]).toEqual({ transactionId: 1, subcategoryId: 102 });
    resetTransactionMocks();
  });

  it("목은 확정한 만큼 미확정에서 빼고 남은 건수를 알려 준다", () => {
    resetTransactionMocks();
    const before = toPendingTransactions(pendingTransactionsMock()).items;
    const request = toSuggestedBulkRequest(before);

    const result = classifyTransactionsBulkMock(request);
    expect(result.confirmed).toBe(request.items.length);
    expect(result.pendingRemain).toBe(before.length - request.items.length);
    expect(pendingTransactionsMock().items.map((item) => item.id)).not.toContain(request.items[0].transactionId);
    resetTransactionMocks();
  });

  it("한 건이라도 확정할 수 없으면 아무것도 저장하지 않는다(서버와 같은 전체 되돌림)", () => {
    resetTransactionMocks();
    const before = toPendingTransactions(pendingTransactionsMock()).items;
    const request = toSuggestedBulkRequest(before);
    const withMissing = { items: [...request.items, { transactionId: 999999, subcategoryId: 102 }] };

    let code: string | null = null;
    try {
      classifyTransactionsBulkMock(withMissing);
    } catch (error) {
      code = error instanceof ApiError ? error.code : "NOT_API_ERROR";
    }

    expect(code).toBe("TRANSACTION_007");
    expect(pendingTransactionsMock().items.length).toBe(before.length);
    resetTransactionMocks();
  });
});
