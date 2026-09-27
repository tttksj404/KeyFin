import { useRouter } from "expo-router";
import { ChartLine, MessageCircle, SendHorizontal, WifiOff } from "lucide-react-native";
import * as React from "react";
import { FlatList, Image, Pressable, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { KeyboardAvoidingView } from "@/components/ui/keyboard-avoiding-view";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useChatHistory, useSendChatMessage } from "@/features/coaching/api/queries";
import { boldSegments } from "@/features/coaching/boldSegments";
import { CoachingBalanceTable } from "@/features/coaching/components/CoachingBalanceTable";
import { CoachingNumericTable } from "@/features/coaching/components/CoachingNumericTable";
import { CoachingSpendingTable } from "@/features/coaching/components/CoachingSpendingTable";
import { chatErrorMessage, isCoachRejected } from "@/features/coaching/errors";
import { CHAT_MESSAGE_MAX_LENGTH, validateChatMessage, type ChatMessage } from "@/features/coaching/model";
import { useCoachingChatScroll } from "@/features/coaching/useCoachingChatScroll";
import { COACH_CAT } from "@/features/room/assets";
import { flattenPending, usePendingTransactions } from "@/features/transaction/api/queries";
import { formatDateTime, parseKSTLocalDateTime } from "@/lib/date";
import { cn } from "@/lib/utils";

const HOME_ROUTE = "/";
const CLEANUP_ROUTE = "/transaction/pending";
const CHART_ROUTE = "/coaching/chart";
export const CHART_LINK_LABEL = "예산 예측 차트 보기";
export const COACH_TITLE = "코치";
export const CHAT_INPUT_LABEL = "코치에게 물어보기";
export const SEND_LABEL = "보내기";
/** 답을 기다리는 동안 코치 자리에 두는 말풍선 */
export const THINKING_LABEL = "코치가 생각하고 있어요";
/** NativeWind className 은 RN Image 에 적용되지 않아 크기만 style 로 준다 */
const AVATAR_STYLE = { width: 36, height: 36 } as const;
/** 내 질문 말풍선은 화면 폭의 85% 를 넘지 않는다(비율 값이라 style 로 준다) */
const BUBBLE_MAX_STYLE = { maxWidth: "85%" } as const;
/** 말풍선 글자는 본문 토큰 `text-body`(16/24) 다 — 2026-09-22 에 11/16 으로 줄였다가 작아서 읽기 어렵다는 요청으로 16 으로 올렸다(2026-09-23). */

export function cleanupLinkLabel(pendingCount: number, pendingMore = false): string {
  return `미확정 결제 ${pendingCount}건${pendingMore ? "+" : ""} 정리`;
}

/** 목록 한 줄. 서버 이력과, 보내는 중인 질문·기다리는 답변을 같은 모양으로 그린다 */
type ChatRow =
  | { key: string; kind: "message"; message: ChatMessage }
  | { key: string; kind: "thinking" }
  /** retryable=false 는 코칭 서버가 그 질문을 거절한 것(AI_003) — 같은 질문을 다시 보내지 않고 입력창에서 다르게 묻는다 */
  | { key: string; kind: "error"; message: string; retryable: boolean };

type PendingTurn = { questionIndex: number; question: string; attempt: number };

/**
 * PAGE-31 코칭 대화 (FR-AI-04, P1). 홈의 코치 고양이를 누르면 들어온다(2026-09-22 사용자 요청 — 그 전까지는 임시 "?" 말풍선).
 * GET /coaching/chat 이력을 그대로 보여 주고, 질문은 POST 한 턴씩이다. 세션은 서버가 잇는다(24시간·20회).
 * 코치 말투·문구는 서버가 만들고 앱은 만들지 않는다(docs/frontend-spec.md 비즈니스 규칙) — 빈 화면 안내는 앱 문구, 답변은 전부 서버 문구다.
 * 답을 기다리는 동안 보낸 질문을 먼저 보여 주고, 실패하면 입력값을 살려 둔 채 그 자리에 다시 시도를 둔다(돈이 움직이지 않아 다시 보내도 된다).
 * 홈 코치에 있던 '미확정 결제 n건 정리' 링크(2026-09-13 사용자 결정)는 여기 상단으로 옮겼다.
 * Pencil 미대조(시안 없음). 내 질문만 오른쪽 `bg-primary` 말풍선이고, 코치 답변은 말풍선 없이 고양이 얼굴 아래 바탕에 그대로 적는다
 * (2026-09-22 사용자 요청 — 처음엔 얼굴 옆 bg-card 말풍선이었는데 폰 폭에서 글이 세로로 길게 늘어졌다).
 * 소비 조회 집계(rows·totalKrw)와 위험·가정 표 데이터(numericRows)는 답변 아래 표로 보여 준다. GET 이력에는 둘 다 없어 재조회 후에는 본문·차트만 남는다.
 * 답변에 예산 예측 차트가 딸리면(chartId) 글 아래 '차트 보기' 버튼이 PAGE-31B 로 간다 — 차트 HTML 은 한 페이지라 말풍선에 넣지 않는다.
 */
function CoachingChatScreen() {
  const router = useRouter();
  const history = useChatHistory();
  const send = useSendChatMessage();
  const pending = usePendingTransactions();
  const [draft, setDraft] = React.useState("");
  const [turn, setTurn] = React.useState<PendingTurn | null>(null);
  const nextAttempt = React.useRef(0);
  const listRef = React.useRef<FlatList<ChatRow>>(null);

  // 캐시 갱신이 mutation 성공 알림보다 먼저 와도 질문과 대기 행을 중복 표시하지 않는다.
  const turnCommitted = turn !== null
    && history.data?.messages[turn.questionIndex]?.role === "user"
    && history.data.messages[turn.questionIndex].content === turn.question
    && history.data.messages[turn.questionIndex + 1]?.role === "assistant";
  const waitingForReply = turn !== null && send.isPending && !turnCommitted;
  const scrollRequestId = turn?.attempt ?? 0;
  const chatScroll = useCoachingChatScroll(listRef, scrollRequestId, history.isSuccess && (turn === null || waitingForReply));

  const pendingCount = flattenPending(pending.data).length;
  const validation = validateChatMessage(draft);
  const canSend = history.isSuccess && validation.ok && !send.isPending;

  const submit = () => {
    if (!history.isSuccess || !validation.ok || send.isPending) return;
    setTurn({ questionIndex: history.data.messages.length, question: validation.message, attempt: ++nextAttempt.current });
    send.mutate(validation.message, { onSuccess: () => setDraft(""), onSettled: chatScroll.cancelRequest });
  };
  const retry = () => {
    if (turn === null || send.isPending) return;
    setTurn({ ...turn, attempt: ++nextAttempt.current });
    send.mutate(turn.question, { onSuccess: () => setDraft(""), onSettled: chatScroll.cancelRequest });
  };

  const rows = React.useMemo<ChatRow[]>(() => {
    const messages = history.data?.messages ?? [];
    const list: ChatRow[] = messages.map((message, index) => ({ key: `m-${index}`, kind: "message", message }));
    // 보낸 질문은 답이 올 때까지(성공 시 캐시에 붙는다) 여기서만 보인다. 실패하면 질문 아래에 다시 시도를 둔다.
    if (turn !== null && !turnCommitted && (send.isPending || send.isError)) {
      list.push({
        key: `m-${turn.questionIndex}`,
        kind: "message",
        message: { role: "user", content: turn.question, chartId: null, rows: [], totalKrw: null, numericRows: null, envelopeBalances: [] },
      });
      list.push(
        send.isPending
          ? { key: `m-${turn.questionIndex + 1}`, kind: "thinking" }
          : { key: `m-${turn.questionIndex + 1}`, kind: "error", message: chatErrorMessage(send.error), retryable: !isCoachRejected(send.error) }
      );
    }
    return list;
  }, [history.data, send.isPending, send.isError, send.error, turn, turnCommitted]);

  const expiresAt = history.data?.expiresAt ?? null;
  const goBack = () => {
    chatScroll.cancel();
    if (router.canGoBack()) router.back();
    else router.replace(HOME_ROUTE);
  };
  const openChart = (chartId: string) => {
    chatScroll.cancel();
    router.push(`${CHART_ROUTE}/${chartId}`);
  };

  return (
    <Screen>
      <ScreenHeader title={COACH_TITLE} onBack={goBack} />
      <KeyboardAvoidingView className="flex-1">
        {history.isPending ? (
          <ChatSkeleton />
        ) : history.isError ? (
          <View className="flex-1 justify-center pb-20">
            <EmptyState
              icon={WifiOff}
              title="대화를 불러오지 못했어요"
              description={chatErrorMessage(history.error)}
              action={{ label: "다시 시도", onPress: () => history.refetch(), disabled: history.isFetching }}
            />
          </View>
        ) : (
          <ScreenFlatList
            testID="coaching-chat-list"
            ref={listRef}
            // 스크롤해도 헤더가 흐려지지 않게 한다 — 대화는 계속 아래로 쌓여 헤더가 늘 사라져 있었고, 뒤로 가기를 누를 수 없었다(사용자 요청 2026-09-23)
            overlapHeader={false}
            data={rows}
            keyExtractor={(row) => row.key}
            contentContainerClassName="px-6 pb-4"
            renderItem={({ item, index }) => (
              <View className={rowSpacingClass(item, index)}>
                <ChatRowView row={item} onRetry={retry} onOpenChart={openChart} />
              </View>
            )}
            onContentSizeChange={chatScroll.onContentSizeChange}
            onLayout={chatScroll.onLayout}
            onScroll={chatScroll.onScroll}
            onScrollBeginDrag={chatScroll.cancel}
            ListFooterComponent={<View key={scrollRequestId} onLayout={chatScroll.onRequestLayout} />}
            keyboardShouldPersistTaps="handled"
            ListHeaderComponent={
              <View className="gap-3 pb-1">
                {pendingCount > 0 ? (
                  <Pressable
                    accessibilityRole="link"
                    accessibilityLabel={cleanupLinkLabel(pendingCount, pending.hasNextPage)}
                    hitSlop={6}
                    onPress={() => router.push(CLEANUP_ROUTE)}
                    className="self-start rounded-lg bg-accent px-3.5 py-2 active:opacity-80"
                  >
                    <Text className="text-body text-primary">{cleanupLinkLabel(pendingCount, pending.hasNextPage)}</Text>
                  </Pressable>
                ) : null}
                {expiresAt !== null ? (
                  <Text className="text-caption text-muted-foreground">
                    이 대화는 {formatDateTime(parseKSTLocalDateTime(expiresAt))}까지 이어져요
                  </Text>
                ) : null}
              </View>
            }
            ListEmptyComponent={
              <EmptyState
                icon={MessageCircle}
                title="코치에게 물어보세요"
                description="이번 달 소비, 다음 달 결제 준비, 궁금한 금융 용어를 물을 수 있어요."
              />
            }
          />
        )}
        <ChatComposer
          value={draft}
          onChange={setDraft}
          onInputFocus={chatScroll.onInputFocus}
          onSubmit={submit}
          disabled={!canSend}
          sending={send.isPending}
          tooLong={!validation.ok && validation.reason === "too_long"}
        />
      </KeyboardAvoidingView>
    </Screen>
  );
}

/**
 * 질문·답변 한 쌍은 붙이고(12) 새 질문이 시작되는 곳만 넓게(40) 띄워 대화가 묻고 답한 단위로 끊겨 보이게 한다(사용자 요청 2026-09-23).
 * 목록 전체 gap 으로는 쌍 안팎을 구분할 수 없어 줄마다 위 여백으로 준다.
 */
function rowSpacingClass(row: ChatRow, index: number): string {
  if (index === 0) return "";
  const isQuestion = row.kind === "message" && row.message.role === "user";
  return isQuestion ? "pt-10" : "pt-3";
}

type ChatRowViewProps = { row: ChatRow; onRetry: () => void; onOpenChart: (chartId: string) => void };

function ChatRowView({ row, onRetry, onOpenChart }: ChatRowViewProps) {
  if (row.kind === "thinking") {
    return (
      <CoachReply>
        <Text className="text-body text-muted-foreground" accessibilityLiveRegion="polite">
          {THINKING_LABEL}
        </Text>
      </CoachReply>
    );
  }
  if (row.kind === "error") {
    return (
      <CoachReply>
        <Text className="text-body text-destructive" accessibilityLiveRegion="polite">
          {row.message}
        </Text>
        {row.retryable ? (
          <Pressable accessibilityRole="button" accessibilityLabel="다시 시도" hitSlop={6} onPress={onRetry} className="self-start">
            <Text className="text-body text-primary">
              다시 시도
            </Text>
          </Pressable>
        ) : null}
      </CoachReply>
    );
  }
  const { message } = row;
  const { chartId } = message;
  if (message.role === "user") {
    return (
      <View className="self-end rounded-2xl bg-primary px-4 py-3" style={BUBBLE_MAX_STYLE} accessibilityRole="text">
        <Text className="text-body text-primary-foreground">
          {message.content}
        </Text>
      </View>
    );
  }
  const hasTable =
    message.rows.length > 0 || message.totalKrw !== null || message.numericRows !== null || message.envelopeBalances.length > 0;
  return (
    <CoachReply wide={hasTable}>
      <Text className="text-body text-foreground">
        {boldSegments(message.content).map((segment, index) =>
          segment.bold ? (
            <Text key={index} className="font-bold">
              {segment.text}
            </Text>
          ) : (
            segment.text
          ),
        )}
      </Text>
      <CoachingSpendingTable rows={message.rows} totalKrw={message.totalKrw} />
      <CoachingNumericTable numericRows={message.numericRows} />
      <CoachingBalanceTable envelopeBalances={message.envelopeBalances} />
      {chartId === null ? null : (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={CHART_LINK_LABEL}
          hitSlop={6}
          onPress={() => onOpenChart(chartId)}
          className="flex-row items-center gap-1.5 self-start rounded-lg bg-accent px-3.5 py-2 active:opacity-80"
        >
          <Icon as={ChartLine} size={16} className="text-primary" />
          <Text className="text-body text-primary">
            {CHART_LINK_LABEL}
          </Text>
        </Pressable>
      )}
    </CoachReply>
  );
}

/** 코치(고양이) 답변 — 고양이 얼굴 아래에 말풍선 카드 없이 바탕에 그대로 적는다(2026-09-22 사용자 요청). 카드가 없으니 폭 제한도 없다 */
// 코치 답변도 내 질문처럼 말풍선으로 감싼다(사용자 요청 2026-09-23). 흰 카드 면 + 그림자이고 고양이 쪽 위 모서리만 덜 둥글게 해 말하는 쪽을 가리킨다.
// 표가 붙은 답변(wide)은 85% 폭이면 금액 열이 두 줄로 꺾여 화면 폭 가득 쓴다.
function CoachReply({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <View className="gap-1.5">
      <Image source={COACH_CAT} style={AVATAR_STYLE} resizeMode="contain" accessible={false} />
      <View
        className={cn(
          "gap-2 rounded-2xl rounded-tl-sm bg-card px-4 py-3 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none",
          wide ? "self-stretch" : "self-start"
        )}
        style={wide ? undefined : BUBBLE_MAX_STYLE}
        accessibilityRole="text"
      >
        {children}
      </View>
    </View>
  );
}

type ChatComposerProps = {
  value: string;
  onChange: (next: string) => void;
  onInputFocus: () => void;
  onSubmit: () => void;
  disabled: boolean;
  sending: boolean;
  tooLong: boolean;
};

// 입력칸이 화면 바닥에 너무 붙어 있어(Android edge-to-edge 는 시스템 내비 바와도 겹친다) 아래 여백을 16 → 32pt 로 올렸다(사용자 요청 2026-09-23).
// 입력칸은 보내기 버튼과 같은 높이(h-touch)로 가로 가운데를 맞추고, 여러 줄 입력의 placeholder 는 Android 에서 위로 붙어 세로 가운데로 잡는다.
// placeholder 는 기본(50%)보다 흐리게 30% 로 (같은 날 요청).
function ChatComposer({ value, onChange, onInputFocus, onSubmit, disabled, sending, tooLong }: ChatComposerProps) {
  return (
    <View className="gap-1 border-t border-border bg-background px-6 pb-8 pt-3">
      <View className="flex-row items-center gap-2">
        <Input
          className="h-touch max-h-32 flex-1 placeholder:text-card-foreground/30"
          value={value}
          onChangeText={onChange}
          onFocus={onInputFocus}
          onPressIn={onInputFocus}
          placeholder="이번 달 외식 얼마 남았어?"
          accessibilityLabel={CHAT_INPUT_LABEL}
          multiline
          textAlignVertical="center"
          maxLength={CHAT_MESSAGE_MAX_LENGTH}
          editable={!sending}
          returnKeyType="send"
          blurOnSubmit
          onSubmitEditing={onSubmit}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={SEND_LABEL}
          accessibilityState={{ disabled, busy: sending }}
          disabled={disabled}
          onPress={onSubmit}
          hitSlop={8}
          className={cn("h-touch w-touch items-center justify-center rounded-full bg-primary active:opacity-80", disabled && "opacity-50")}
        >
          <Icon as={SendHorizontal} size={20} className="text-primary-foreground" />
        </Pressable>
      </View>
      {tooLong ? <Text className="text-caption text-destructive">질문은 {CHAT_MESSAGE_MAX_LENGTH}자까지 보낼 수 있어요.</Text> : null}
    </View>
  );
}

function ChatSkeleton() {
  return (
    <View className="flex-1 gap-3 px-6" accessibilityLabel="대화를 불러오는 중">
      <Skeleton className="h-16 w-3/4 self-start rounded-lg" />
      <Skeleton className="h-10 w-1/2 self-end rounded-2xl" />
      <Skeleton className="h-20 w-4/5 self-start rounded-lg" />
    </View>
  );
}

export { CoachingChatScreen };
