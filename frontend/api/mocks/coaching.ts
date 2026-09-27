import { ApiError } from "@/api/error";
import { MOCK_CHART_HTML, MOCK_CHART_ID } from "@/api/mocks/coaching-chart";
import type { ChatHistoryDto, ChatMessageDto, ChatReplyDto } from "@/features/coaching/model";
import { getKSTParts } from "@/lib/date";

/**
 * GET·POST /coaching/chat 목 (배포 서버 Swagger · 백엔드 CoachingChatService, 2026-09-22).
 * 서버처럼 세션을 하나 들고 있다: 첫 질문에 세션이 열려 24시간 뒤 만료 시각이 잡히고, 그 뒤 질문·답변이 이력에 쌓인다.
 * 답변은 질문에 예측·위험·다음 달·괜찮 이 들어가면 COACHING, 소비 조회는 CHAT(engine 집계), 일반 안내는 CHAT(llm) 이다.
 * 답을 못 하는 경우도 본다: 주식·코인 투자·로또 는 out_of_scope 안내 문구(template), 자모·기호만 있는 질문은 코칭 서버 거절(422 AI_003).
 * COACHING 답변에는 예산 예측 차트 id(MOCK_CHART_ID)를, 소비 조회 답변에는 rows·totalKrw를 붙인다. GET 이력에는 집계를 넣지 않는다.
 * 위험(위험·괜찮)·가정(만약·사면) 답변에는 봉투별 표 데이터 numericRows 를 붙인다(ai/coaching/docs/chat.md numeric_rows, 2026-09-23).
 */
const SESSION_HOURS = 24;
const UNAVAILABLE_MESSAGE = "코치가 잠시 자리를 비웠어요. 잠시 후 다시 시도해 주세요.";
const REJECTED_MESSAGE = "질문을 이해하지 못했어요. 조금 다르게 물어봐 주세요.";
const CHART_NOT_FOUND_MESSAGE = "차트를 찾을 수 없어요.";
/** 한글 음절·영숫자가 하나도 없는 질문(ㅋㅋㅋ · ??? 등) — 코칭 서버가 이해하지 못해 거절하는 경우로 본다 */
const GIBBERISH = /^[^가-힣A-Za-z0-9]+$/;

type MockSession = { messages: ChatMessageDto[]; expiresAt: string };

let session: MockSession | null = null;
let unavailable = false;

function pad2(value: number): string {
  return value.toString().padStart(2, "0");
}

function kstLocalDateTime(date: Date): string {
  const p = getKSTParts(date);
  return `${p.year}-${pad2(p.month)}-${pad2(p.day)}T${pad2(p.hour)}:${pad2(p.minute)}:${pad2(p.second)}`;
}

function answer(message: string): ChatReplyDto {
  const id = `mock-${Date.now()}`;
  if (/주식|코인 투자|로또/.test(message)) {
    return {
      reply: "투자 종목 추천은 제가 도울 수 없는 영역이에요. 대신 이번 달 소비나 다음 달 결제 준비는 같이 볼 수 있어요.",
      kind: "CHAT",
      status: "out_of_scope",
      source: "template",
      fallbackReason: null,
      answerId: id,
      rows: [],
      totalKrw: null,
      numericRows: null,
    };
  }
  if (/만약|사면|산다면/.test(message)) {
    return {
      reply: "그 구매를 더하면 이번 달 취미 봉투는 예상 소비가 150,000원 안팎이라 예산 안에서 끝날 가능성이 높아요. 다만 외식은 230,000원까지 갈 수 있어요.",
      kind: "COACHING",
      status: "answered",
      source: "engine",
      fallbackReason: null,
      answerId: id,
      chartId: MOCK_CHART_ID,
      rows: [],
      totalKrw: null,
      numericRows: {
        mode: "what_if",
        envelopeSpend: [
          { envelope: "외식", p10Krw: 90_000, p50Krw: 150_000, p90Krw: 230_000 },
          { envelope: "취미", p10Krw: 110_000, p50Krw: 150_000, p90Krw: 190_000 },
        ],
        budgetRisk: [],
      },
    };
  }
  if (/예측|위험|다음 달|괜찮/.test(message)) {
    return {
      reply: "다음 달 25일 카드 대금 214,000원이 나가는데 결제 계좌 잔액이 180,000원이라 34,000원이 모자라요. 20일까지 준비 이체를 잡아 두면 안전해요.",
      kind: "COACHING",
      status: "answered",
      source: "engine",
      fallbackReason: null,
      answerId: id,
      chartId: MOCK_CHART_ID,
      rows: [],
      totalKrw: null,
      numericRows: {
        mode: "risk",
        envelopeSpend: [
          { envelope: "외식", p10Krw: 90_000, p50Krw: 150_000, p90Krw: 230_000 },
          { envelope: "교통", p10Krw: 40_000, p50Krw: 52_000, p90Krw: 70_000 },
        ],
        budgetRisk: [
          { envelope: "외식", budgetKrw: 200_000, observedUsedKrw: 136_300, projectedUsedP50Krw: 210_000, pOverBudget: 0.62 },
          { envelope: "교통", budgetKrw: 60_000, observedUsedKrw: 31_000, projectedUsedP50Krw: 52_000, pOverBudget: 0.18 },
        ],
      },
    };
  }
  if (/얼마.*(?:썼|쓴|사용)|(?:소비|지출|사용)\s*(?:내역|금액)/.test(message)) {
    return {
      reply: "이번 달 외식에 45,000원, 교통에 12,000원을 써서 총 57,000원을 썼어요.",
      kind: "CHAT",
      status: "answered",
      source: "engine",
      fallbackReason: null,
      answerId: id,
      rows: [
        { envelope: "외식", totalKrw: 45_000, count: 3 },
        { envelope: "교통", totalKrw: 12_000, count: 4 },
      ],
      totalKrw: 57_000,
      numericRows: null,
    };
  }
  return {
    reply: "이번 달 외식 봉투는 120,000원 중 84,500원을 썼어요. 남은 35,500원으로 열흘을 보내려면 하루 3,500원 정도예요.",
    kind: "CHAT",
    status: "answered",
    source: "llm",
    fallbackReason: null,
    answerId: id,
    rows: [],
    totalKrw: null,
    numericRows: null,
  };
}

export function chatHistoryMock(): ChatHistoryDto {
  if (unavailable) throw new ApiError(503, "AI_001", UNAVAILABLE_MESSAGE);
  if (session === null) return { messages: [], expiresAt: null };
  return { messages: session.messages.map((m) => ({ ...m })), expiresAt: session.expiresAt };
}

export function sendChatMock(message: string): ChatReplyDto {
  if (unavailable) throw new ApiError(503, "AI_001", UNAVAILABLE_MESSAGE);
  if (message.trim() === "" || message.length > 2000) throw new ApiError(400, "COMMON_001", "입력값이 올바르지 않습니다.");
  if (GIBBERISH.test(message.trim())) throw new ApiError(422, "AI_003", REJECTED_MESSAGE);
  if (session === null) {
    session = { messages: [], expiresAt: kstLocalDateTime(new Date(Date.now() + SESSION_HOURS * 60 * 60 * 1000)) };
  }
  const reply = answer(message);
  session.messages.push({ role: "user", content: message }, { role: "assistant", content: reply.reply, chartId: reply.chartId ?? null });
  return reply;
}

/**
 * GET /coaching/charts/{chartId}/html 목 (백엔드 develop CoachingChatController, 2026-09-23 확정).
 * 목 id 하나만 있고 나머지는 404 AI_002 다(다른 소유자의 차트도 같은 404).
 */
export function chartHtmlMock(chartId: string): string {
  if (unavailable) throw new ApiError(503, "AI_001", UNAVAILABLE_MESSAGE);
  if (chartId !== MOCK_CHART_ID) throw new ApiError(404, "AI_002", CHART_NOT_FOUND_MESSAGE);
  return MOCK_CHART_HTML;
}

/** 코칭 서버가 자리를 비운 상황(503 AI_001)을 흉내 낸다 */
export function setCoachingUnavailableMock(next: boolean): void {
  unavailable = next;
}

export function resetCoachingMocks(): void {
  session = null;
  unavailable = false;
}
