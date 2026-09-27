import { api, isMocked } from "@/api/client";
import { chartHtmlMock, chatHistoryMock, sendChatMock } from "@/api/mocks/coaching";
import { withMockLatency } from "@/api/mocks/latency";
import {
  toChartHtml,
  toChatHistory,
  toChatReply,
  type ChatHistory,
  type ChatHistoryDto,
  type ChatReply,
  type ChatReplyDto,
  type ChatRequestDto,
} from "@/features/coaching/model";

/**
 * GET /coaching/chat — 현재 세션의 대화 이력 (FR-AI-04, PAGE-31). 세션이 없거나 만료됐으면 messages 빈 배열·expiresAt null.
 * 오류: 503 AI_001(코칭 서버 응답 없음).
 */
export async function getChatHistory(signal?: AbortSignal): Promise<ChatHistory> {
  if (isMocked("coaching")) return toChatHistory(await withMockLatency(chatHistoryMock(), signal));
  const { data } = await api.get<ChatHistoryDto>("/coaching/chat", { signal });
  return toChatHistory(data);
}

/**
 * POST /coaching/chat — 코치에게 질문 한 턴. 세션은 서버가 잇는다(24시간·20회, 만료되면 새 세션).
 * 오류: 400 COMMON_001(비었거나 2000자 초과) · 422 AI_003(코칭 서버가 질문을 거절 — 다시 보내도 같다) · 503 AI_001. 돈이 움직이지 않으므로 화면에서 다시 시도해도 된다.
 */
export async function sendChatMessage(message: string): Promise<ChatReply> {
  if (isMocked("coaching")) return toChatReply(await withMockLatency(sendChatMock(message)));
  const body: ChatRequestDto = { message };
  const { data } = await api.post<ChatReplyDto>("/coaching/chat", body);
  return toChatReply(data);
}

/**
 * GET /coaching/charts/{chartId}/html — 예산 예측 차트를 자기완결 HTML 로 받는다(AI 서버 `/v1/charts/{id}/html` 을 백엔드가 중계).
 * 경로·오류 코드는 백엔드 develop 으로 확정(2026-09-23). 응답이 JSON 봉투가 아니라 문서라
 * text 로 받고, 인터셉터의 unwrapEnvelope 는 문자열을 그대로 돌려준다. 오류: 404 AI_002(없거나 다른 계정) · 422 AI_003 · 503 AI_001.
 */
export async function getChartHtml(chartId: string, signal?: AbortSignal): Promise<string> {
  if (isMocked("coaching")) return toChartHtml(await withMockLatency(chartHtmlMock(chartId), signal));
  const { data } = await api.get<string>(`/coaching/charts/${encodeURIComponent(chartId)}/html`, {
    signal,
    responseType: "text",
    headers: { Accept: "text/html" },
  });
  return toChartHtml(data);
}
