import { ContractMismatchError } from "@/lib/contract";
import { KST_LOCAL_DATE_TIME } from "@/lib/date";
import { fromServerWon, type KRW } from "@/lib/money";

/**
 * 코칭 대화 계약 (배포 서버 Swagger `/api/v1/coaching/chat`, 백엔드 develop CoachingChatController, 2026-09-22 대조. FR-AI-04 · PAGE-31).
 * 세션은 서버가 사용자당 하나 관리하고(24시간·질문 20회) 만료되면 새 세션으로 이어진다 — 앱은 세션 id 를 모른다.
 * kind·status·source 는 코칭 서버 값을 그대로 넘겨주므로 모르는 값은 UNKNOWN 으로 흡수한다 (규칙 90).
 */

/** 서버 @Size(max = 2000). 비면 400 COMMON_001 */
export const CHAT_MESSAGE_MAX_LENGTH = 2000;

/** CHAT = 금융 개념·소비 조회·안내, COACHING = 예측·위험 코칭 */
export const CHAT_KINDS = ["CHAT", "COACHING"] as const;
export type ChatKind = (typeof CHAT_KINDS)[number] | "UNKNOWN";

/**
 * 코칭 서버 상태 그대로. answered 외에는 답을 못 한 이유다 —
 * needs_source(근거 자료 없음) · needs_data(개인 자료 부족) · needs_clarification(지원하지 않는 기간·필터) · out_of_scope(금융 외) · unavailable(모델 실패, fallbackReason 참고).
 * COACHING 은 서버가 항상 answered 로 준다.
 */
export const CHAT_STATUSES = ["answered", "needs_source", "needs_data", "needs_clarification", "out_of_scope", "unavailable"] as const;
export type ChatStatus = (typeof CHAT_STATUSES)[number] | "UNKNOWN";

/** llm = 모델 문장, template = 안내 문구, engine = 확정 원장 집계 */
export const CHAT_SOURCES = ["llm", "template", "engine"] as const;
export type ChatSource = (typeof CHAT_SOURCES)[number] | "UNKNOWN";

export const CHAT_ROLES = ["user", "assistant"] as const;
export type ChatRole = (typeof CHAT_ROLES)[number] | "UNKNOWN";

export type ChatRequestDto = { message: string };

export type ChatSpendingRowDto = { envelope: string; totalKrw: number; count: number };
export type ChatSpendingRow = { envelope: string; totalKrw: KRW; count: number };

/** 봉투가 둘 이상인 대화 답변의 봉투별 장부 잔액 표(서버 envelopeBalances). 본문에는 표 설명 한 줄만 있다. */
export type ChatEnvelopeBalanceDto = { envelope: string; balanceKrw: number };
export type ChatEnvelopeBalance = { envelope: string; balanceKrw: KRW };

/**
 * 위험(risk)·가정(what_if) 코칭 답변의 봉투별 구조화 행 (ai/coaching/docs/chat.md `numeric_rows` · 백엔드 ChatReply.NumericRows, 2026-09-23 대조).
 * 엔진이 이미 계산한 값을 서버가 그대로 노출하므로 앱도 그대로 표로 그린다. 그 외 답변과 GET 이력은 null 이다.
 */
export const NUMERIC_ROWS_MODES = ["risk", "what_if"] as const;
export type NumericRowsMode = (typeof NUMERIC_ROWS_MODES)[number] | "UNKNOWN";

export type ChatEnvelopeSpendRowDto = { envelope: string; p10Krw: number; p50Krw: number; p90Krw: number };
export type ChatBudgetRiskRowDto = {
  envelope: string;
  budgetKrw: number;
  observedUsedKrw: number;
  projectedUsedP50Krw: number;
  /** 0~1 확률 */
  pOverBudget: number;
};
export type ChatNumericRowsDto = {
  mode: string | null;
  /** 두 모드 모두. 봉투별 예측 소비 분위수. 근거가 없으면 빈 배열(백엔드는 null 도 빈 배열로 내린다) */
  envelopeSpend: ChatEnvelopeSpendRowDto[] | null;
  /** 위험 답변에서 스냅샷에 봉투 예산이 있을 때만. 없으면 빈 배열 */
  budgetRisk: ChatBudgetRiskRowDto[] | null;
};

export type ChatEnvelopeSpendRow = { envelope: string; p10Krw: KRW; p50Krw: KRW; p90Krw: KRW };
export type ChatBudgetRiskRow = { envelope: string; budgetKrw: KRW; observedUsedKrw: KRW; projectedUsedP50Krw: KRW; pOverBudget: number };
export type ChatNumericRows = { mode: NumericRowsMode; envelopeSpend: ChatEnvelopeSpendRow[]; budgetRisk: ChatBudgetRiskRow[] };

export type ChatReplyDto = {
  reply: string;
  kind: string;
  status: string | null;
  source: string | null;
  fallbackReason: string | null;
  answerId: string | null;
  /** 답변에 예산 예측 차트가 딸렸을 때 그 id. 없으면 undefined·null */
  chartId?: string | null;
  /** 소비 조회 답변의 봉투별 집계. 그 외 답변은 빈 배열·null */
  rows: ChatSpendingRowDto[];
  totalKrw: number | null;
  /** 위험·가정 답변의 봉투별 표 데이터. 그 외 답변은 null (이 필드가 없던 응답은 undefined) */
  numericRows?: ChatNumericRowsDto | null;
  /** 봉투별 장부 잔액 표. 그 외 답변은 빈 배열 (이 필드가 없던 응답은 undefined) */
  envelopeBalances?: ChatEnvelopeBalanceDto[] | null;
};

/** GET 이력에는 소비 집계(rows·totalKrw)와 표 데이터(numericRows)가 포함되지 않는다 */
export type ChatMessageDto = { role: string; content: string; chartId?: string | null };

export type ChatHistoryDto = {
  messages: ChatMessageDto[];
  /** "2026-09-23T10:00:00" (KST). 세션이 없거나 만료됐으면 null */
  expiresAt: string | null;
};

export type ChatReply = {
  reply: string;
  kind: ChatKind;
  status: ChatStatus;
  source: ChatSource;
  fallbackReason: string | null;
  answerId: string | null;
  /** 실제 답변인지. 아니면 status 가 못 한 이유다 */
  isAnswered: boolean;
  /** 딸린 예산 예측 차트. 모양이 아니면 없는 것으로 본다 */
  chartId: string | null;
  rows: ChatSpendingRow[];
  totalKrw: KRW | null;
  numericRows: ChatNumericRows | null;
  envelopeBalances: ChatEnvelopeBalance[];
};

export type ChatMessage = {
  role: ChatRole;
  content: string;
  chartId: string | null;
  rows: ChatSpendingRow[];
  totalKrw: KRW | null;
  numericRows: ChatNumericRows | null;
  envelopeBalances: ChatEnvelopeBalance[];
};

export type ChatHistory = {
  messages: ChatMessage[];
  expiresAt: string | null;
  /** 살아 있는 세션이 있어 이어서 묻는 중인지 */
  hasSession: boolean;
};

function toUnion<T extends string>(values: readonly T[], raw: string | null | undefined): T | "UNKNOWN" {
  return typeof raw === "string" && (values as readonly string[]).includes(raw) ? (raw as T) : "UNKNOWN";
}

function won(value: number, field: string): KRW {
  try {
    return fromServerWon(value);
  } catch {
    throw new ContractMismatchError(field);
  }
}

function toSpendingRow(dto: ChatSpendingRowDto): ChatSpendingRow {
  if (typeof dto?.envelope !== "string") throw new ContractMismatchError("rows.envelope");
  if (!Number.isSafeInteger(dto.count) || dto.count < 0) throw new ContractMismatchError("rows.count");
  return { envelope: dto.envelope, totalKrw: won(dto.totalKrw, "rows.totalKrw"), count: dto.count };
}

function toEnvelopeBalance(dto: ChatEnvelopeBalanceDto): ChatEnvelopeBalance {
  if (typeof dto?.envelope !== "string") throw new ContractMismatchError("envelopeBalances.envelope");
  return { envelope: dto.envelope, balanceKrw: won(dto.balanceKrw, "envelopeBalances.balanceKrw") };
}

function toEnvelopeSpendRow(dto: ChatEnvelopeSpendRowDto): ChatEnvelopeSpendRow {
  if (typeof dto?.envelope !== "string") throw new ContractMismatchError("numericRows.envelopeSpend.envelope");
  return {
    envelope: dto.envelope,
    p10Krw: won(dto.p10Krw, "numericRows.envelopeSpend.p10Krw"),
    p50Krw: won(dto.p50Krw, "numericRows.envelopeSpend.p50Krw"),
    p90Krw: won(dto.p90Krw, "numericRows.envelopeSpend.p90Krw"),
  };
}

function toBudgetRiskRow(dto: ChatBudgetRiskRowDto): ChatBudgetRiskRow {
  if (typeof dto?.envelope !== "string") throw new ContractMismatchError("numericRows.budgetRisk.envelope");
  const p = dto.pOverBudget;
  if (typeof p !== "number" || !Number.isFinite(p) || p < 0 || p > 1) throw new ContractMismatchError("numericRows.budgetRisk.pOverBudget");
  return {
    envelope: dto.envelope,
    budgetKrw: won(dto.budgetKrw, "numericRows.budgetRisk.budgetKrw"),
    observedUsedKrw: won(dto.observedUsedKrw, "numericRows.budgetRisk.observedUsedKrw"),
    projectedUsedP50Krw: won(dto.projectedUsedP50Krw, "numericRows.budgetRisk.projectedUsedP50Krw"),
    pOverBudget: p,
  };
}

/** 위험·가정 답변의 표 데이터. 없으면(null·필드 없음) null 이고, 행 목록이 null 이면 빈 배열로 본다 */
export function toNumericRows(dto: ChatNumericRowsDto | null | undefined): ChatNumericRows | null {
  if (dto === null || dto === undefined) return null;
  if (typeof dto !== "object") throw new ContractMismatchError("numericRows");
  const envelopeSpend = dto.envelopeSpend ?? [];
  const budgetRisk = dto.budgetRisk ?? [];
  if (!Array.isArray(envelopeSpend)) throw new ContractMismatchError("numericRows.envelopeSpend");
  if (!Array.isArray(budgetRisk)) throw new ContractMismatchError("numericRows.budgetRisk");
  return {
    mode: toUnion(NUMERIC_ROWS_MODES, dto.mode),
    envelopeSpend: envelopeSpend.map(toEnvelopeSpendRow),
    budgetRisk: budgetRisk.map(toBudgetRiskRow),
  };
}

export function toChatReply(dto: ChatReplyDto): ChatReply {
  if (typeof dto.reply !== "string") throw new ContractMismatchError("reply");
  const rows = dto.rows ?? [];
  if (!Array.isArray(rows)) throw new ContractMismatchError("rows");
  const envelopeBalances = dto.envelopeBalances ?? [];
  if (!Array.isArray(envelopeBalances)) throw new ContractMismatchError("envelopeBalances");
  const status = toUnion(CHAT_STATUSES, dto.status);
  return {
    reply: dto.reply,
    kind: toUnion(CHAT_KINDS, dto.kind),
    status,
    source: toUnion(CHAT_SOURCES, dto.source),
    fallbackReason: dto.fallbackReason ?? null,
    answerId: dto.answerId ?? null,
    isAnswered: status === "answered",
    chartId: parseChartId(dto.chartId ?? undefined),
    rows: rows.map(toSpendingRow),
    totalKrw: dto.totalKrw == null ? null : won(dto.totalKrw, "totalKrw"),
    numericRows: toNumericRows(dto.numericRows),
    envelopeBalances: envelopeBalances.map(toEnvelopeBalance),
  };
}

export function toChatMessage(dto: ChatMessageDto): ChatMessage {
  if (typeof dto.content !== "string") throw new ContractMismatchError("messages.content");
  return {
    role: toUnion(CHAT_ROLES, dto.role),
    content: dto.content,
    chartId: parseChartId(dto.chartId ?? undefined),
    rows: [],
    totalKrw: null,
    numericRows: null,
    envelopeBalances: [],
  };
}

export function toChatHistory(dto: ChatHistoryDto): ChatHistory {
  if (dto.expiresAt !== null && dto.expiresAt !== undefined && !KST_LOCAL_DATE_TIME.test(dto.expiresAt)) {
    throw new ContractMismatchError("expiresAt");
  }
  const expiresAt = dto.expiresAt ?? null;
  return { messages: (dto.messages ?? []).map(toChatMessage), expiresAt, hasSession: expiresAt !== null };
}

export const EMPTY_CHAT_HISTORY: ChatHistory = { messages: [], expiresAt: null, hasSession: false };

export type ChatMessageValidation = { ok: true; message: string } | { ok: false; reason: "empty" | "too_long" };

/** 보내기 전에 서버 규칙(공백만이면 400, 2000자 초과 400)을 미리 걸러 헛된 요청을 막는다. 앞뒤 공백은 잘라 보낸다 */
export function validateChatMessage(raw: string): ChatMessageValidation {
  const message = raw.trim();
  if (message === "") return { ok: false, reason: "empty" };
  if (message.length > CHAT_MESSAGE_MAX_LENGTH) return { ok: false, reason: "too_long" };
  return { ok: true, message };
}

/**
 * 답변을 받은 뒤 이력 캐시에 질문·답변 한 턴을 붙인다 — 이력을 다시 받지 않아도 화면이 이어진다.
 * 세션 만료 시각은 서버만 알아서(만료 뒤 첫 질문이면 새 세션) 그대로 두고, 세션이 없던 상태였으면 있는 것으로 본다.
 * 소비 집계·표 데이터는 POST 응답을 캐시에 보관하는 동안만 표시한다. GET 이력으로 재조회하면 둘 다 없다.
 */
export function appendChatTurn(history: ChatHistory, question: string, reply: ChatReply): ChatHistory {
  return {
    ...history,
    messages: [
      ...history.messages,
      { role: "user", content: question, chartId: null, rows: [], totalKrw: null, numericRows: null, envelopeBalances: [] },
      { role: "assistant", content: reply.reply, chartId: reply.chartId, rows: reply.rows, totalKrw: reply.totalKrw, numericRows: reply.numericRows, envelopeBalances: reply.envelopeBalances },
    ],
    hasSession: true,
  };
}

/**
 * 예산 예측 차트 (AI 서버 `POST /v1/charts/budget-forecast` 결과를 백엔드가 HTML 로 중계 — 2026-09-22 팀 결정, 2026-09-23 백엔드 확정).
 * 답변·이력의 chartId 로 `GET /coaching/charts/{chartId}/html` 을 받아 WebView 에 그린다.
 */

/** AI 서버 차트 id 는 uuid4().hex(32자)지만 백엔드가 감쌀 수 있어 URL 에 안전한 글자 64자까지 받는다 */
const CHART_ID = /^[A-Za-z0-9_-]{1,64}$/;

/** 차트 라우트의 id 파라미터. 모양이 아니면 null (규칙 50: 파라미터는 믿지 않는다) */
export function parseChartId(value: string | string[] | undefined): string | null {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw !== undefined && CHART_ID.test(raw) ? raw : null;
}

/** 중계된 차트 HTML. 문서가 아니면(빈 문자열·JSON) 계약 불일치다 */
export function toChartHtml(raw: unknown): string {
  if (typeof raw !== "string" || !/<html[\s>]/i.test(raw)) throw new ContractMismatchError("chart html");
  return raw;
}
