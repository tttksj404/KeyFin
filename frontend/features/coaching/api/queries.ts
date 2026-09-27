import { queryOptions, skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getChartHtml, getChatHistory, sendChatMessage } from "@/features/coaching/api/coaching.api";
import { isChartNotFoundError } from "@/features/coaching/errors";
import { appendChatTurn, EMPTY_CHAT_HISTORY, type ChatHistory } from "@/features/coaching/model";

export const coachingKeys = {
  all: ["coaching"] as const,
  chat: () => [...coachingKeys.all, "chat"] as const,
  chart: (chartId: string) => [...coachingKeys.all, "chart", chartId] as const,
};

/** 저장된 차트는 바뀌지 않아 한동안 캐시를 쓴다 */
const CHART_STALE_MS = 5 * 60 * 1000;
const CHART_RETRY_MAX = 2;

/** 세션은 서버가 24시간 잇지만 다른 기기에서 물었을 수도 있어 화면에 들어올 때마다 새로 받는다 */
export function chatHistoryQueryOptions() {
  return queryOptions({
    queryKey: coachingKeys.chat(),
    queryFn: ({ signal }) => getChatHistory(signal),
    staleTime: 0,
  });
}

/** 코칭 대화(PAGE-31) 이력 */
export function useChatHistory() {
  return useQuery(chatHistoryQueryOptions());
}

/**
 * 코치에게 질문 한 턴. 답이 오면 이력 캐시에 질문·답변을 붙여 화면이 바로 이어지고, 실패하면 캐시를 건드리지 않아 입력값을 살려 다시 보낼 수 있다.
 * 코칭 서버가 느릴 수 있어(백엔드 read-timeout 60초) 자동 재시도는 하지 않는다 — 같은 질문이 두 번 세션에 쌓인다.
 */
export function useSendChatMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: sendChatMessage,
    retry: false,
    onSuccess: (reply, question) => {
      queryClient.setQueryData<ChatHistory>(coachingKeys.chat(), (current) =>
        appendChatTurn(current ?? EMPTY_CHAT_HISTORY, question, reply)
      );
    },
  });
}

/** 예산 예측 차트 HTML. id 가 없으면(라우트 파라미터가 모양이 아니면) 요청하지 않고, 404 는 다시 시도하지 않는다 */
export function useChartHtml(chartId: string | null) {
  return useQuery({
    queryKey: coachingKeys.chart(chartId ?? ""),
    queryFn: chartId === null ? skipToken : ({ signal }) => getChartHtml(chartId, signal),
    staleTime: CHART_STALE_MS,
    retry: (failureCount, error) => !isChartNotFoundError(error) && failureCount < CHART_RETRY_MAX,
  });
}
