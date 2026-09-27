import { ApiError } from "@/api/error";
import { chartHtmlMock, chatHistoryMock, resetCoachingMocks, sendChatMock, setCoachingUnavailableMock } from "@/api/mocks/coaching";
import { MOCK_CHART_ID } from "@/api/mocks/coaching-chart";
import { chartErrorMessage, chatErrorMessage, isChartNotFoundError, isCoachRejected, isCoachUnavailable } from "@/features/coaching/errors";
import {
  appendChatTurn,
  CHAT_MESSAGE_MAX_LENGTH,
  EMPTY_CHAT_HISTORY,
  parseChartId,
  toChartHtml,
  toChatHistory,
  toChatReply,
  toNumericRows,
  validateChatMessage,
  type ChatBudgetRiskRowDto,
  type ChatNumericRowsDto,
  type ChatReplyDto,
  type ChatSpendingRowDto,
} from "@/features/coaching/model";
import { ContractMismatchError } from "@/lib/contract";

const replyDto: ChatReplyDto = {
  reply: "이번 달 외식 봉투는 120,000원 중 84,500원을 썼어요.",
  kind: "CHAT",
  status: "answered",
  source: "llm",
  fallbackReason: null,
  answerId: "ans-1",
  rows: [],
  totalKrw: null,
  numericRows: null,
};

describe("coaching model", () => {
  it("답변 DTO 를 화면 모델로 바꾸고 answered 만 실제 답변으로 본다", () => {
    expect(toChatReply(replyDto)).toEqual({ ...replyDto, isAnswered: true, chartId: null, envelopeBalances: [] });
    const declined = toChatReply({ ...replyDto, kind: "COACHING", status: "needs_data", source: "template" });
    expect(declined.isAnswered).toBe(false);
    expect(declined.kind).toBe("COACHING");
  });

  it("모르는 kind·status·source 는 UNKNOWN 으로 흡수하고, reply 가 없으면 계약 불일치다", () => {
    const reply = toChatReply({ ...replyDto, kind: "RANT", status: "thinking", source: "oracle" });
    expect([reply.kind, reply.status, reply.source]).toEqual(["UNKNOWN", "UNKNOWN", "UNKNOWN"]);
    expect(() => toChatReply({ ...replyDto, reply: undefined as unknown as string })).toThrow(ContractMismatchError);
  });

  it("이력은 세션이 없으면 빈 목록·hasSession false, 있으면 KST 만료 시각을 지킨다", () => {
    expect(toChatHistory({ messages: [], expiresAt: null })).toEqual(EMPTY_CHAT_HISTORY);
    const history = toChatHistory({
      messages: [
        { role: "user", content: "외식 얼마 남았어?" },
        { role: "assistant", content: "35,500원 남았어요." },
        { role: "system", content: "…" },
      ],
      expiresAt: "2026-09-23T10:00:00",
    });
    expect(history.hasSession).toBe(true);
    expect(history.messages.map((m) => m.role)).toEqual(["user", "assistant", "UNKNOWN"]);
    expect(() => toChatHistory({ messages: [], expiresAt: "2026-09-23T10:00:00+09:00" })).toThrow(ContractMismatchError);
  });

  it("질문은 공백을 잘라 1자 이상 2000자 이하일 때만 보낸다", () => {
    expect(validateChatMessage("  외식 얼마 남았어?  ")).toEqual({ ok: true, message: "외식 얼마 남았어?" });
    expect(validateChatMessage("   ")).toEqual({ ok: false, reason: "empty" });
    expect(validateChatMessage("가".repeat(CHAT_MESSAGE_MAX_LENGTH + 1))).toEqual({ ok: false, reason: "too_long" });
  });

  it("답변을 받으면 이력 끝에 질문·답변 한 턴을 붙이고 세션이 있는 것으로 본다", () => {
    const next = appendChatTurn(EMPTY_CHAT_HISTORY, "외식 얼마 남았어?", toChatReply(replyDto));
    expect(next.hasSession).toBe(true);
    expect(next.messages).toEqual([
      { role: "user", content: "외식 얼마 남았어?", chartId: null, rows: [], totalKrw: null, numericRows: null, envelopeBalances: [] },
      { role: "assistant", content: replyDto.reply, chartId: null, rows: [], totalKrw: null, numericRows: null, envelopeBalances: [] },
    ]);
  });
});

describe("소비 조회 집계", () => {
  const rows: ChatSpendingRowDto[] = [
    { envelope: "외식", totalKrw: 45_000, count: 3 },
    { envelope: "교통", totalKrw: 12_000, count: 4 },
  ];

  it("POST 집계를 원화 모델로 변환하고 다음 대화가 추가되어도 기존 집계를 보존한다", () => {
    const reply = toChatReply({ ...replyDto, source: "engine", rows, totalKrw: 57_000 });
    const history = appendChatTurn(EMPTY_CHAT_HISTORY, "이번 달 얼마 썼어?", reply);
    const next = appendChatTurn(history, "금리란 뭐야?", toChatReply(replyDto));

    expect(next.messages[1]).toEqual({
      role: "assistant",
      content: replyDto.reply,
      chartId: null,
      rows: [
        { envelope: "외식", totalKrw: "45000", count: 3 },
        { envelope: "교통", totalKrw: "12000", count: 4 },
      ],
      totalKrw: "57000",
      numericRows: null,
      envelopeBalances: [],
    });
    expect(next.messages[0]).toMatchObject({ rows: [], totalKrw: null });
    expect(next.messages[3]).toMatchObject({ rows: [], totalKrw: null });
    expect(EMPTY_CHAT_HISTORY.messages).toEqual([]);
  });

  it("지출 없는 조회의 0원과 집계 없는 일반 답변의 null을 구분한다", () => {
    expect(toChatReply({ ...replyDto, totalKrw: 0 })).toMatchObject({ rows: [], totalKrw: "0" });
    expect(toChatReply(replyDto)).toMatchObject({ rows: [], totalKrw: null });
    expect(toChatReply({ ...replyDto, rows: [{ envelope: "외식", totalKrw: 0, count: 0 }], totalKrw: 0 })).toMatchObject({
      rows: [{ envelope: "외식", totalKrw: "0", count: 0 }],
      totalKrw: "0",
    });
  });

  it("집계 필드가 없는 이전 POST 응답도 본문을 보여 준다", () => {
    const { rows: _rows, totalKrw: _totalKrw, ...legacy } = replyDto;
    expect(toChatReply(legacy as ChatReplyDto)).toMatchObject({ reply: replyDto.reply, rows: [], totalKrw: null });
  });

  it("GET 이력은 집계 없이 변환하되 기존 chartId는 유지한다", () => {
    const history = toChatHistory({
      messages: [{ role: "assistant", content: "답변", chartId: MOCK_CHART_ID }],
      expiresAt: "2026-09-23T10:00:00",
    });
    expect(history.messages[0]).toEqual({ role: "assistant", content: "답변", chartId: MOCK_CHART_ID, rows: [], totalKrw: null, numericRows: null, envelopeBalances: [] });
  });

  it.each([1.5, Number.NaN, Number.MAX_SAFE_INTEGER + 1, "45000", null])("잘못된 행 금액 %p는 계약 오류로 처리한다", (amount) => {
    expect(() => toChatReply({ ...replyDto, rows: [{ ...rows[0], totalKrw: amount as number }] })).toThrow(ContractMismatchError);
  });

  it.each([1.5, Number.NaN, Number.MAX_SAFE_INTEGER + 1, "57000"])("잘못된 합계 %p는 계약 오류로 처리한다", (amount) => {
    expect(() => toChatReply({ ...replyDto, totalKrw: amount as number })).toThrow(ContractMismatchError);
  });

  it.each([-1, 1.5, Number.MAX_SAFE_INTEGER + 1, "3"])("잘못된 건수 %p는 계약 오류로 처리한다", (count) => {
    expect(() => toChatReply({ ...replyDto, rows: [{ ...rows[0], count: count as number }] })).toThrow(ContractMismatchError);
  });

  it("배열이 아닌 집계와 봉투명이 없는 행은 계약 오류로 처리한다", () => {
    expect(() => toChatReply({ ...replyDto, rows: {} as ChatSpendingRowDto[] })).toThrow(ContractMismatchError);
    expect(() => toChatReply({ ...replyDto, rows: [null as unknown as ChatSpendingRowDto] })).toThrow(ContractMismatchError);
  });
});

describe("위험·가정 표 데이터(numericRows)", () => {
  const riskDto: ChatNumericRowsDto = {
    mode: "risk",
    envelopeSpend: [{ envelope: "외식", p10Krw: 90_000, p50Krw: 150_000, p90Krw: 230_000 }],
    budgetRisk: [{ envelope: "외식", budgetKrw: 200_000, observedUsedKrw: 136_300, projectedUsedP50Krw: 210_000, pOverBudget: 0.62 }],
  };

  it("봉투별 분위수·예산 위험을 원화 모델로 바꾸고 mode 는 그대로 넘긴다", () => {
    expect(toChatReply({ ...replyDto, kind: "COACHING", numericRows: riskDto }).numericRows).toEqual({
      mode: "risk",
      envelopeSpend: [{ envelope: "외식", p10Krw: "90000", p50Krw: "150000", p90Krw: "230000" }],
      budgetRisk: [{ envelope: "외식", budgetKrw: "200000", observedUsedKrw: "136300", projectedUsedP50Krw: "210000", pOverBudget: 0.62 }],
    });
    expect(toNumericRows({ ...riskDto, mode: "what_if", budgetRisk: [] })).toMatchObject({ mode: "what_if", budgetRisk: [] });
  });

  it("표 데이터가 없는 답변(null·필드 없음)과 이전 응답은 null 이고, 행 목록이 null 이면 빈 배열이다", () => {
    expect(toChatReply({ ...replyDto, numericRows: null }).numericRows).toBeNull();
    const { numericRows: _numericRows, ...legacy } = replyDto;
    expect(toChatReply(legacy as ChatReplyDto).numericRows).toBeNull();
    expect(toNumericRows({ mode: "risk", envelopeSpend: null, budgetRisk: null })).toEqual({ mode: "risk", envelopeSpend: [], budgetRisk: [] });
  });

  it("봉투별 장부 잔액 표를 그대로 옮기고, 없거나 null 이면 빈 배열로 본다", () => {
    const reply = toChatReply({
      ...replyDto,
      envelopeBalances: [
        { envelope: "외식", balanceKrw: 343700 },
        { envelope: "기타", balanceKrw: -5000 },
      ],
    });
    expect(reply.envelopeBalances).toEqual([
      { envelope: "외식", balanceKrw: "343700" },
      { envelope: "기타", balanceKrw: "-5000" },
    ]);
    expect(toChatReply({ ...replyDto, envelopeBalances: null }).envelopeBalances).toEqual([]);
    expect(toChatReply(replyDto).envelopeBalances).toEqual([]);
    expect(() => toChatReply({ ...replyDto, envelopeBalances: [{ envelope: "외식", balanceKrw: 1.5 }] })).toThrow(ContractMismatchError);
  });

  it("모르는 mode 는 UNKNOWN 으로 흡수하되 행은 그대로 쓴다", () => {
    expect(toNumericRows({ ...riskDto, mode: "forecast" })).toMatchObject({ mode: "UNKNOWN", envelopeSpend: [{ envelope: "외식" }] });
    expect(toNumericRows({ ...riskDto, mode: null })).toMatchObject({ mode: "UNKNOWN" });
  });

  it("확률은 0~1 사이 숫자만 받고, 봉투명·금액·배열 모양이 다르면 계약 불일치다", () => {
    const risk = riskDto.budgetRisk![0];
    for (const pOverBudget of [-0.1, 1.2, Number.NaN, "0.5" as unknown as number, undefined as unknown as number]) {
      expect(() => toNumericRows({ ...riskDto, budgetRisk: [{ ...risk, pOverBudget }] })).toThrow(ContractMismatchError);
    }
    expect(toNumericRows({ ...riskDto, budgetRisk: [{ ...risk, pOverBudget: 0 }] })!.budgetRisk[0].pOverBudget).toBe(0);
    expect(toNumericRows({ ...riskDto, budgetRisk: [{ ...risk, pOverBudget: 1 }] })!.budgetRisk[0].pOverBudget).toBe(1);
    expect(() => toNumericRows({ ...riskDto, budgetRisk: [{ ...risk, envelope: 3 as unknown as string }] })).toThrow(ContractMismatchError);
    expect(() => toNumericRows({ ...riskDto, budgetRisk: [{ ...risk, budgetKrw: 1.5 }] })).toThrow(ContractMismatchError);
    expect(() => toNumericRows({ ...riskDto, envelopeSpend: [{ envelope: "외식", p10Krw: 1, p50Krw: "2" as unknown as number, p90Krw: 3 }] })).toThrow(
      ContractMismatchError
    );
    expect(() => toNumericRows({ ...riskDto, envelopeSpend: {} as ChatNumericRowsDto["envelopeSpend"] })).toThrow(ContractMismatchError);
    expect(() => toNumericRows({ ...riskDto, budgetRisk: [null as unknown as ChatBudgetRiskRowDto] })).toThrow(ContractMismatchError);
  });

  it("답변을 붙이면 표 데이터가 그 턴에만 남고 질문·GET 이력에는 없다", () => {
    const reply = toChatReply({ ...replyDto, kind: "COACHING", numericRows: riskDto });
    const history = appendChatTurn(EMPTY_CHAT_HISTORY, "이번 달 위험해?", reply);
    expect(history.messages[0].numericRows).toBeNull();
    expect(history.messages[1].numericRows).toEqual(reply.numericRows);
    const next = appendChatTurn(history, "금리란 뭐야?", toChatReply(replyDto));
    expect(next.messages[1].numericRows).toEqual(reply.numericRows);
    expect(next.messages[3].numericRows).toBeNull();
  });
});

describe("coaching errors", () => {
  it("AI_001 은 코치 부재 문구, 400 은 길이 안내, 그 밖은 서버 문구를 쓴다", () => {
    const unavailable = new ApiError(503, "AI_001", "코치가 잠시 자리를 비웠어요. 잠시 후 다시 시도해 주세요.");
    expect(isCoachUnavailable(unavailable)).toBe(true);
    expect(chatErrorMessage(unavailable)).toBe("코치가 잠시 자리를 비웠어요. 잠시 후 다시 시도해 주세요.");
    expect(chatErrorMessage(new ApiError(400, "COMMON_001", "입력값이 올바르지 않습니다."))).toBe(
      "질문은 1자 이상 2000자 이하로 적어 주세요."
    );
    expect(chatErrorMessage(new ApiError(500, "COMMON_006", "서버 내부 오류"))).toBe("서버 내부 오류");
    expect(chatErrorMessage(new Error("boom"))).toBe("답변을 받지 못했어요. 다시 시도해 주세요.");
  });

  it("422 AI_003 은 코칭 서버의 거절이라 다르게 묻는 문구이고, 부재(AI_001)와 구분한다", () => {
    const rejected = new ApiError(422, "AI_003", "질문을 이해하지 못했어요. 조금 다르게 물어봐 주세요.");
    expect(chatErrorMessage(rejected)).toBe("질문을 이해하지 못했어요. 조금 다르게 물어봐 주세요.");
    expect(isCoachRejected(rejected)).toBe(true);
    expect(isCoachUnavailable(rejected)).toBe(false);
    expect(isCoachRejected(new ApiError(503, "AI_001", ""))).toBe(false);
    expect(isCoachRejected(new Error("boom"))).toBe(false);
  });
});

describe("coaching mocks", () => {
  beforeEach(() => resetCoachingMocks());

  it("소비 조회 POST에는 집계가 있고 GET 이력에는 없다", () => {
    const reply = sendChatMock("이번 달 얼마 썼어?");
    expect(reply).toMatchObject({
      kind: "CHAT",
      source: "engine",
      rows: [
        { envelope: "외식", totalKrw: 45_000, count: 3 },
        { envelope: "교통", totalKrw: 12_000, count: 4 },
      ],
      totalKrw: 57_000,
    });
    expect(chatHistoryMock().messages[1]).toEqual({ role: "assistant", content: reply.reply, chartId: null });
  });

  it.each(["소비란 뭐야?", "다음 달 괜찮아?", "주식 뭐 살까?"])("소비 조회가 아닌 '%s'에는 집계가 없다", (question) => {
    expect(sendChatMock(question)).toMatchObject({ rows: [], totalKrw: null });
  });

  it("위험 답변에는 risk 표 데이터(예산 위험 포함), 가정 답변에는 what_if 표 데이터가 있고 그 외는 null 이다", () => {
    const risk = sendChatMock("이번 달 위험해?");
    expect(risk.kind).toBe("COACHING");
    expect(risk.numericRows?.mode).toBe("risk");
    expect(risk.numericRows?.envelopeSpend?.[0]).toMatchObject({ envelope: "외식", p50Krw: 150_000 });
    expect(risk.numericRows?.budgetRisk?.[0]).toMatchObject({ envelope: "외식", pOverBudget: 0.62 });
    expect(toChatReply(risk).numericRows?.budgetRisk).toHaveLength(2);
    const whatIf = sendChatMock("만약 게임기를 사면?");
    expect(whatIf.numericRows).toMatchObject({ mode: "what_if", budgetRisk: [] });
    expect(sendChatMock("이번 달 얼마 썼어?").numericRows).toBeNull();
    expect(sendChatMock("소비란 뭐야?").numericRows).toBeNull();
    expect(chatHistoryMock().messages.every((m) => !("numericRows" in m))).toBe(true);
  });

  it("첫 질문에 세션이 열리고 질문·답변이 이력에 쌓인다", () => {
    expect(chatHistoryMock()).toEqual({ messages: [], expiresAt: null });
    const reply = sendChatMock("다음 달 괜찮아?");
    expect(reply.kind).toBe("COACHING");
    const history = chatHistoryMock();
    expect(history.expiresAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/);
    expect(history.messages).toEqual([
      { role: "user", content: "다음 달 괜찮아?" },
      { role: "assistant", content: reply.reply, chartId: MOCK_CHART_ID },
    ]);
  });

  it("자모·기호만 있는 질문은 422 AI_003 거절이고 세션에 쌓이지 않는다", () => {
    for (const gibberish of ["ㅋㅋㅋ", "???", "ㅁㄴㅇㄹ !!"]) {
      let rejected: unknown;
      try {
        sendChatMock(gibberish);
      } catch (error) {
        rejected = error;
      }
      expect(rejected).toBeInstanceOf(ApiError);
      expect((rejected as ApiError).status).toBe(422);
      expect(isCoachRejected(rejected)).toBe(true);
    }
    expect(chatHistoryMock()).toEqual({ messages: [], expiresAt: null });
    expect(sendChatMock("ㅋㅋ 외식 얼마 남았어?").status).toBe("answered");
  });

  it("금융 밖 질문은 out_of_scope 안내이고, 코칭 서버가 없으면 503 AI_001 이다", () => {
    expect(sendChatMock("주식 뭐 살까?").status).toBe("out_of_scope");
    setCoachingUnavailableMock(true);
    expect(() => sendChatMock("외식 얼마 남았어?")).toThrow(ApiError);
    expect(() => chatHistoryMock()).toThrow(ApiError);
  });
});

describe("예산 예측 차트(HTML 중계)", () => {
  afterEach(() => resetCoachingMocks());

  it("라우트 파라미터는 URL 안전 글자 64자까지만 차트 id 로 본다", () => {
    expect(parseChartId(MOCK_CHART_ID)).toBe(MOCK_CHART_ID);
    expect(parseChartId([MOCK_CHART_ID, "other"])).toBe(MOCK_CHART_ID);
    expect(parseChartId(undefined)).toBeNull();
    expect(parseChartId("")).toBeNull();
    expect(parseChartId("../etc")).toBeNull();
    expect(parseChartId("a".repeat(65))).toBeNull();
  });

  it("HTML 문서만 받고, 빈 문자열·JSON 은 계약 불일치다", () => {
    const html = chartHtmlMock(MOCK_CHART_ID);
    expect(toChartHtml(html)).toBe(html);
    expect(() => toChartHtml("")).toThrow(ContractMismatchError);
    expect(() => toChartHtml('{"chart":{}}')).toThrow(ContractMismatchError);
    expect(() => toChartHtml(null)).toThrow(ContractMismatchError);
  });

  it("답변·이력의 chartId 는 모양이 맞을 때만 남고, 목의 COACHING 답변에는 차트가 딸린다", () => {
    expect(toChatReply({ ...replyDto, chartId: MOCK_CHART_ID }).chartId).toBe(MOCK_CHART_ID);
    expect(toChatReply({ ...replyDto, chartId: "../x" }).chartId).toBeNull();
    expect(toChatReply(replyDto).chartId).toBeNull();
    const coaching = toChatReply(sendChatMock("다음 달 괜찮아?"));
    expect(coaching.kind).toBe("COACHING");
    expect(coaching.chartId).toBe(MOCK_CHART_ID);
    const history = toChatHistory(chatHistoryMock());
    expect(history.messages.map((m) => m.chartId)).toEqual([null, MOCK_CHART_ID]);
    const appended = appendChatTurn(EMPTY_CHAT_HISTORY, "q", coaching);
    expect(appended.messages[1]?.chartId).toBe(MOCK_CHART_ID);
  });

  it("모르는 id 는 404 AI_002 로 못 찾음이고(코드로 판정), 코칭 서버 부재는 대화와 같은 문구다", () => {
    let notFound: unknown;
    try {
      chartHtmlMock("0000");
    } catch (error) {
      notFound = error;
    }
    expect(notFound).toBeInstanceOf(ApiError);
    expect((notFound as ApiError).code).toBe("AI_002");
    expect(isChartNotFoundError(notFound)).toBe(true);
    expect(chartErrorMessage(notFound)).toBe("차트를 찾을 수 없어요.");
    expect(isChartNotFoundError(new ApiError(404, "UNKNOWN", ""))).toBe(false);
    expect(isChartNotFoundError(new ApiError(503, "AI_001", ""))).toBe(false);
    expect(chartErrorMessage(new ApiError(503, "AI_001", "x"))).toBe(chatErrorMessage(new ApiError(503, "AI_001", "x")));
    expect(chartErrorMessage(new Error("boom"))).toBe("차트를 불러오지 못했어요. 다시 시도해 주세요.");
  });
});
