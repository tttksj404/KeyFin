import { QueryClient, QueryClientProvider, type QueryKey } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react-native";

import { budgetKeys } from "@/features/budget/api/queries";
import { linkKeys } from "@/features/link/api/queries";
import * as notificationApi from "@/features/notification/api/notification.api";
import { notificationKeys, usePushForegroundDisplay } from "@/features/notification/api/queries";
import { COACH_FEEDBACK_POLL_MS, resetCoachFeedbackRequests } from "@/features/notification/coachFeedback";
import { PUSH_DATA_TYPES, type PushDataType } from "@/features/notification/model";
import * as push from "@/features/notification/push";
import { useCoachSpeechStore } from "@/features/notification/store";
import { paymentKeys } from "@/features/payment/api/queries";
import { roomKeys } from "@/features/room/api/queries";
import { shopKeys } from "@/features/shop/api/queries";
import { transactionKeys } from "@/features/transaction/api/queries";

const relatedKeys: Record<PushDataType, QueryKey[]> = {
  CLASSIFY_QUESTION: [transactionKeys.all],
  BUDGET_ALERT: [budgetKeys.current(), roomKeys.home()],
  TRANSFER_REQUEST: [paymentKeys.transfers()],
  COACHING: [transactionKeys.all],
  REACTION: [],
  CLEANUP: [transactionKeys.all],
  NEW_LINK_FOUND: [linkKeys.candidates()],
  PAYMENT_RISK: [paymentKeys.calendar()],
  WARNING: [paymentKeys.calendar()],
  COIN_GRANTED: [shopKeys.coins(), roomKeys.home()],
  SUBSCRIPTION_CARD: [paymentKeys.fixedExpenses()],
  UNKNOWN: [],
};

const removeSubscription = jest.fn();
let client: QueryClient;
let fetchFeedback: jest.SpiedFunction<typeof notificationApi.getCoachFeedback>;
let onReceived: (data: unknown) => void;

async function receive(type: string, notificationId = "41") {
  await act(async () => {
    // 이전 구독의 제목·본문 인자가 들어와도 직접 복사 경로가 되살아나지 않아야 한다.
    Reflect.apply(onReceived, undefined, [
      { type, notificationId },
      { title: "식비 봉투를 초과했어요", body: "이 푸시 문구는 말풍선에 담지 않아요" },
    ]);
  });
}

async function foreground() {
  return renderHook(() => usePushForegroundDisplay(true), {
    wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
}

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  resetCoachFeedbackRequests();
  useCoachSpeechStore.setState({ latest: null });
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  jest.spyOn(push, "canUsePush").mockReturnValue(true);
  jest.spyOn(push, "setForegroundPushHandler").mockResolvedValue();
  jest.spyOn(push, "subscribePushReceived").mockImplementation(async (listener) => {
    onReceived = listener;
    return removeSubscription;
  });
  fetchFeedback = jest.spyOn(notificationApi, "getCoachFeedback").mockResolvedValue({ status: "NONE", text: null });
});

afterEach(() => {
  client.clear();
  resetCoachFeedbackRequests();
  useCoachSpeechStore.setState({ latest: null });
  jest.restoreAllMocks();
  jest.useRealTimers();
});

it.each([...PUSH_DATA_TYPES, "FUTURE_TYPE"] as const)("%s 푸시는 OS 표시 준비와 캐시 갱신을 유지하고 제목·본문을 말풍선에 복사하지 않는다", async (type) => {
  const typeKey = type === "FUTURE_TYPE" ? "UNKNOWN" : type;
  const expectedKeys = [notificationKeys.all, ...relatedKeys[typeKey]];
  for (const queryKey of expectedKeys) client.setQueryData(queryKey, { cached: true });
  await foreground();

  await receive(type);

  expect(useCoachSpeechStore.getState().latest).toBeNull();
  for (const queryKey of expectedKeys) expect(client.getQueryState(queryKey)?.isInvalidated).toBe(true);
  expect(fetchFeedback).toHaveBeenCalledTimes(type === "BUDGET_ALERT" ? 1 : 0);
  expect(push.setForegroundPushHandler).toHaveBeenCalledTimes(1);
});

it("예산 푸시는 AI가 준비될 때까지 말풍선을 만들지 않고 READY 본문만 표시한다", async () => {
  fetchFeedback.mockResolvedValueOnce({ status: "PENDING", text: null })
    .mockResolvedValueOnce({ status: "READY", text: "이번 주에는 외식 횟수를 줄여보면 좋겠다냥." });
  await foreground();

  await receive("BUDGET_ALERT");
  expect(useCoachSpeechStore.getState().latest).toBeNull();
  await act(async () => { jest.advanceTimersByTime(COACH_FEEDBACK_POLL_MS - 1); });
  expect(fetchFeedback).toHaveBeenCalledTimes(1);
  await act(async () => { jest.advanceTimersByTime(1); });

  expect(fetchFeedback).toHaveBeenNthCalledWith(2, 41);
  expect(useCoachSpeechStore.getState().latest?.text).toBe("이번 주에는 외식 횟수를 줄여보면 좋겠다냥.");
});

it("일반 푸시가 도착해도 이미 받은 AI 코칭을 덮어쓰지 않는다", async () => {
  useCoachSpeechStore.getState().announce("읽고 있던 AI 코칭");
  const previous = useCoachSpeechStore.getState().latest;
  await foreground();

  await receive("COACHING");

  expect(useCoachSpeechStore.getState().latest).toBe(previous);
  expect(fetchFeedback).not.toHaveBeenCalled();
});

it("로그인 구독이 해제되면 푸시 수신 리스너도 제거한다", async () => {
  const hook = await foreground();

  await hook.unmount();

  expect(removeSubscription).toHaveBeenCalledTimes(1);
});
