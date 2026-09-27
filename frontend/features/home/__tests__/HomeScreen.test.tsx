import { focusManager, notifyManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import * as React from "react";
import { AppState, type AppStateStatus } from "react-native";

import { authUserMock } from "@/api/mocks/auth";
import { budgetConfirmedMock, budgetProposedMock } from "@/api/mocks/budget";
import { paymentCalendarEmptyMock, paymentCalendarMock } from "@/api/mocks/payment";
import { attendanceMock, roomMock } from "@/api/mocks/room";
import { pendingTransactionsMock } from "@/api/mocks/transaction";
import { useAuthStore } from "@/features/auth/store";
import { getCurrentBudget } from "@/features/budget/api/budget.api";
import { PROPOSAL_FROM_HOME_HREF } from "@/features/budget/components/BudgetProposalScreen";
import { toBudget } from "@/features/budget/model";
import { ROOM_LABEL } from "@/features/home/components/CharacterRoom";
import { COACH_SPEECH_CLOSE_LABEL, COACH_SPEECH_ICON_LABEL } from "@/features/home/components/CoachTarget";
import { COACHING_CHAT_ROUTE } from "@/features/home/components/HomeCoach";
import { HOME_HELP_LABEL, HOME_ROOM_BOX_TEST_ID, HomeScreen } from "@/features/home/components/HomeScreen";
import { getPaymentCalendar } from "@/features/payment/api/payment.api";
import { toPaymentCalendar } from "@/features/payment/model";
import { SPOTLIGHT_LABEL } from "@/features/home/components/RoomGuideOverlay";
import { ROOM_GUIDE_STEPS } from "@/features/home/useRoomGuide";
import { COACH_SPEECH_OPEN_MS } from "@/features/home/useCoachSpeech";
import { useCoachSpeechStore } from "@/features/notification/store";
import { checkAttendance, getRoom } from "@/features/room/api/room.api";
import { roomKeys } from "@/features/room/api/queries";
import { ROOM_VIEW_TEST_ID } from "@/features/room/components/RoomView";
import { toAttendance, toRoom, type Room } from "@/features/room/model";
import { getPendingTransactions } from "@/features/transaction/api/transaction.api";
import { transactionKeys } from "@/features/transaction/api/queries";
import { toPendingTransactions } from "@/features/transaction/model";

jest.mock("@/features/room/api/room.api", () => ({ getRoom: jest.fn(), checkAttendance: jest.fn() }));
jest.mock("@/features/budget/api/budget.api", () => ({ getCurrentBudget: jest.fn() }));
jest.mock("@/features/payment/api/payment.api", () => ({ getPaymentCalendar: jest.fn() }));
jest.mock("@/features/transaction/api/transaction.api", () => ({
  getPendingTransactions: jest.fn(),
}));

// 테스트에는 그림을 읽어 주는 Skia 가 없어 방 씬이 영영 '준비 중'이다. 그러면 홈이 방 대기 덮개를 걷지 않으므로
// 씬을 "다 그린 상태"로 바꿔 둔다 — 방 데이터가 와서 씬이 올라가는 순간 준비됐다고 알린다.
const mockSceneMount = jest.fn();
const mockSceneUnmount = jest.fn();
const mockRoomLock = jest.fn();
jest.mock("@/features/home/components/CharacterRoom", () => {
  const ReactActual = jest.requireActual<typeof import("react")>("react");
  const actual = jest.requireActual<typeof import("@/features/home/components/CharacterRoom")>("@/features/home/components/CharacterRoom");
  return {
    ...actual,
    CharacterRoom: (props: React.ComponentProps<typeof actual.CharacterRoom>) => {
      mockRoomLock(props.locked);
      return ReactActual.createElement(actual.CharacterRoom, props);
    },
  };
});
jest.mock("@/features/room/components/RoomSceneLoader", () => {
  const ReactActual = jest.requireActual<typeof import("react")>("react");
  const { useNotifySceneReady } = jest.requireActual("@/features/room/sceneReady");
  function MockRoomSceneLoader() {
    ReactActual.useEffect(() => {
      mockSceneMount();
      return () => { mockSceneUnmount(); };
    }, []);
    useNotifySceneReady(true);
    return null;
  }
  return { RoomSceneLoader: MockRoomSceneLoader };
});

// 홈 화면은 최종 예산 표시를 검증한다. 실제 시간에 따른 카운트업은 CI 속도에 의존하지 않도록 생략한다.
jest.mock("@/hooks/use-count-up", () => ({ useCountUp: (target: string) => target }));

// 쿼리 알림을 setTimeout 이 아니라 그 자리에서 보내, 목 응답이 act 범위 안에서 화면에 반영되게 한다.
notifyManager.setScheduler((callback) => callback());

const MONTH = "202609";
const TODAY_KEY = "2026-09-08";
const PERIOD = "9월 1일~30일";
jest.mock("@/lib/date", () => ({
  ...jest.requireActual<typeof import("@/lib/date")>("@/lib/date"),
  currentMonthKey: () => "202609",
  currentDateKey: () => "2026-09-08",
}));

const mockPush = jest.fn();
const mockRedirect = jest.fn();
let mockHomeFocused = true;
const mockFocusListeners = new Set<(focused: boolean) => void>();
jest.mock("expo-router", () => {
  const ReactActual = jest.requireActual<typeof import("react")>("react");
  return {
    useRouter: () => ({ push: mockPush }),
    Redirect: ({ href }: { href: unknown }) => {
      mockRedirect(href);
      return null;
    },
    useFocusEffect: (effect: () => void | (() => void)) => ReactActual.useEffect(() => {
      let dispose: void | (() => void);
      const onFocus = (focused: boolean) => {
        dispose?.();
        dispose = focused ? effect() : undefined;
      };
      mockFocusListeners.add(onFocus);
      onFocus(mockHomeFocused);
      return () => {
        mockFocusListeners.delete(onFocus);
        dispose?.();
      };
    }, [effect]),
  };
});

const mockedGetRoom = jest.mocked(getRoom);
const mockedGetBudget = jest.mocked(getCurrentBudget);
const mockedCheckAttendance = jest.mocked(checkAttendance);
const mockedGetCalendar = jest.mocked(getPaymentCalendar);
const mockedGetPending = jest.mocked(getPendingTransactions);

/** 방 폭을 재고, 그 뒤 붙는 오버레이(보드·캘린더·코치)의 조회가 끝날 때까지 기다린다 */
async function layoutRoom() {
  await fireEvent(screen.getByTestId(HOME_ROOM_BOX_TEST_ID), "layout", { nativeEvent: { layout: { width: 327, height: 586 } } });
  await fireEvent(screen.getByTestId(ROOM_VIEW_TEST_ID), "layout", { nativeEvent: { layout: { width: 327, height: 404 } } });
  await waitForQueriesToSettle();
}

const ROOM_GUIDE_KEY = `keyfin.roomGuide.${authUserMock.id}`;

let client: QueryClient;
const appStateListeners = new Set<(state: AppStateStatus) => void>();
let appStateSubscription: jest.SpyInstance;
const originalAppState = AppState.currentState;

async function setHomeFocused(focused: boolean) {
  await act(async () => {
    mockHomeFocused = focused;
    [...mockFocusListeners].forEach((listener) => listener(focused));
  });
  await waitForQueriesToSettle();
}

async function setAppState(state: AppStateStatus) {
  await act(async () => {
    AppState.currentState = state;
    [...appStateListeners].forEach((listener) => listener(state));
  });
}

/** 확정 뒤 무효화로 도는 재조회가 테스트 밖에서 끝나 act 경고를 내지 않도록 기다린다 */
async function waitForQueriesToSettle() {
  await waitFor(() => expect(client.isFetching()).toBe(0));
}

function renderHome(props: { arriving?: boolean } = {}) {
  client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      // 출석 mutation의 기본 5분 GC 타이머가 CI 테스트 종료를 붙잡지 않게 한다.
      mutations: { gcTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <HomeScreen {...props} />
    </QueryClientProvider>
  );
}

describe("HomeScreen", () => {
  beforeEach(async () => {
    mockHomeFocused = true;
    AppState.currentState = "active";
    useCoachSpeechStore.setState({ latest: null });
    appStateSubscription = jest.spyOn(AppState, "addEventListener").mockImplementation((event, listener) => {
      if (event === "change") appStateListeners.add(listener);
      return { remove: () => { appStateListeners.delete(listener); } };
    });
    // 대부분의 테스트는 첫 진입 안내를 이미 본 사용자 기준이다. 안내 자체는 아래 전용 테스트가 기록을 지우고 본다.
    await SecureStore.setItemAsync(ROOM_GUIDE_KEY, "1");
    // 로그인 화면(PAGE-01)이 생기면서 스토어 기본값이 비로그인이 됐다. 홈은 로그인 이후 화면이라 사용자를 넣고 시작한다.
    useAuthStore.setState({ user: authUserMock, status: "authenticated" });
    mockedGetRoom.mockReset();
    mockedGetBudget.mockReset();
    mockedCheckAttendance.mockReset();
    mockedCheckAttendance.mockResolvedValue(toAttendance(attendanceMock));
    mockedGetCalendar.mockReset();
    mockedGetCalendar.mockResolvedValue(toPaymentCalendar(paymentCalendarMock(MONTH)));
    mockedGetPending.mockReset();
    mockedGetPending.mockResolvedValue({ items: [], nextCursor: null });
    mockPush.mockReset();
    mockRedirect.mockReset();
    mockSceneMount.mockClear();
    mockSceneUnmount.mockClear();
    mockRoomLock.mockClear();
  });

  afterEach(async () => {
    await cleanup();
    jest.useRealTimers();
    expect(appStateListeners.size).toBe(0);
    appStateSubscription.mockRestore();
    AppState.currentState = originalAppState;
    useCoachSpeechStore.setState({ latest: null });
  });

  it("말풍선은 방 카메라를 잠그고 홈 이탈 시 읽음 처리 없이 접힌다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    useCoachSpeechStore.getState().announce("첫 코치 메시지");
    const pending = useCoachSpeechStore.getState().latest;
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    expect(screen.getByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeTruthy();
    expect(mockRoomLock).toHaveBeenLastCalledWith(true);
    // 실제 홈 크기가 코치까지 전달되어, 넓은 방 캔버스의 숨겨진 부분에 X가 놓이지 않게 한다.
    await fireEvent(screen.getByTestId(HOME_ROOM_BOX_TEST_ID), "layout", { nativeEvent: { layout: { width: 280, height: 680 } } });
    const placement = screen.getByTestId("coach-speech-placement").props.style;
    expect(placement.left + placement.width + 12 * (379 / 327) - (379 - 280) / 2).toBeCloseTo(272);
    await setHomeFocused(false);
    expect(screen.queryByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeNull();
    expect(mockRoomLock).toHaveBeenLastCalledWith(false);
    expect(useCoachSpeechStore.getState().latest).toEqual(pending);

    await setHomeFocused(true);
    expect(screen.queryByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: `${COACH_SPEECH_ICON_LABEL}, 새 메시지` }));
    expect(screen.getByText("첫 코치 메시지")).toBeTruthy();
    expect(mockRoomLock).toHaveBeenLastCalledWith(true);
    await fireEvent.press(screen.getByRole("button", { name: COACH_SPEECH_CLOSE_LABEL }));
    expect(mockRoomLock).toHaveBeenLastCalledWith(false);
  });

  it("백그라운드에서는 접고, 새 메시지는 앱과 홈이 모두 활성화된 뒤 보여준다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    useCoachSpeechStore.getState().announce("기존 코치 메시지");
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    await setAppState("background");
    expect(screen.queryByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeNull();
    expect(useCoachSpeechStore.getState().latest?.text).toBe("기존 코치 메시지");
    await setAppState("active");
    expect(screen.queryByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: `${COACH_SPEECH_ICON_LABEL}, 새 메시지` }));
    expect(screen.getByText("기존 코치 메시지")).toBeTruthy();
    await setAppState("background");
    expect(screen.queryByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeNull();
    await setHomeFocused(false);
    await act(async () => { useCoachSpeechStore.getState().announce("백그라운드에서 받은 메시지"); });
    await setAppState("active");
    expect(screen.queryByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeNull();
    await setHomeFocused(true);
    expect(screen.getByText("백그라운드에서 받은 메시지")).toBeTruthy();
    expect(screen.getByRole("button", { name: COACH_SPEECH_CLOSE_LABEL })).toBeTruthy();
  });

  it("처음 들어오면 코치가 리스트·캘린더를 차례로 안내하고, 다 보면 다시 나오지 않는다", async () => {
    await SecureStore.deleteItemAsync(ROOM_GUIDE_KEY);
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    const first = await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    expect(await screen.findByText(ROOM_GUIDE_STEPS[0].message)).toBeTruthy();
    // 안내 중에는 가리키는 곳만 남기고 화면을 덮는다 — 덮개는 위·아래·좌·우 네 장이다
    expect(screen.getAllByRole("button", { name: SPOTLIGHT_LABEL })).toHaveLength(4);

    // 마지막 단계까지 차례로 넘긴다
    for (let step = 1; step < ROOM_GUIDE_STEPS.length; step++) {
      await fireEvent.press(screen.getByRole("button", { name: "다음" }));
      expect(screen.getByText(ROOM_GUIDE_STEPS[step].message)).toBeTruthy();
    }
    await fireEvent.press(screen.getByRole("button", { name: "알겠어요" }));
    expect(screen.queryByText(ROOM_GUIDE_STEPS[ROOM_GUIDE_STEPS.length - 1].message)).toBeNull();
    expect(screen.queryByRole("button", { name: SPOTLIGHT_LABEL })).toBeNull();
    await waitFor(async () => expect(await SecureStore.getItemAsync(ROOM_GUIDE_KEY)).toBe("1"));
    await first.unmount();

    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();
    expect(screen.queryByText(ROOM_GUIDE_STEPS[0].message)).toBeNull();
  });

  it("이미 본 안내도 ? 버튼으로 처음부터 다시 볼 수 있다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();
    expect(screen.queryByText(ROOM_GUIDE_STEPS[0].message)).toBeNull();

    await fireEvent.press(await screen.findByRole("button", { name: HOME_HELP_LABEL }));
    expect(screen.getByText(ROOM_GUIDE_STEPS[0].message)).toBeTruthy();

    await fireEvent.press(screen.getByRole("button", { name: "그만 보기" }));
    expect(screen.queryByText(ROOM_GUIDE_STEPS[0].message)).toBeNull();
  });

  it("안내 중에 리스트를 직접 누르면 안내를 끝내고 예산 시트를 연다", async () => {
    await SecureStore.deleteItemAsync(ROOM_GUIDE_KEY);
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();
    await screen.findByText(ROOM_GUIDE_STEPS[0].message);

    await fireEvent.press(screen.getByRole("button", { name: /예산 보드/ }));
    expect(screen.queryByText(ROOM_GUIDE_STEPS[0].message)).toBeNull();
    await waitFor(async () => expect(await SecureStore.getItemAsync(ROOM_GUIDE_KEY)).toBe("1"));
  });

  it.each([false, true])("코치(고양이)를 탭하면 코칭 대화 화면으로 간다 (AI 코칭: %s)", async (hasAi) => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    if (hasAi) useCoachSpeechStore.getState().announce("외식 지출을 확인해 보세요.");
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    await fireEvent.press(await screen.findByRole("button", { name: "코치" }));
    expect(mockPush).toHaveBeenCalledWith(COACHING_CHAT_ROUTE);
  });

  describe("AI 코칭 전용 말풍선", () => {
    const feedback = "외식 예산을 넘었어요. 남은 기간에는 식비 계획을 조정해 보세요.";
    const icon = () => screen.getByRole("button", { name: `${COACH_SPEECH_ICON_LABEL}, 새 메시지` });
    const close = () => screen.getByRole("button", { name: COACH_SPEECH_CLOSE_LABEL });
    const expectNoSpeech = () => {
      expect(screen.queryByTestId("coach-speech-bubble")).toBeNull();
      expect(screen.queryByRole("button", { name: /코치가 할 말 보기/ })).toBeNull();
    };

    beforeEach(() => {
      jest.useFakeTimers();
      mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
      mockedGetRoom.mockResolvedValue(toRoom({
        ...roomMock,
        attendance: { checkedToday: true },
        stickers: { count: 1, total: 1, removableToday: true },
        overEnvelopes: [1],
      }));
    });

    async function showHome() {
      await renderHome();
      // 다른 화면이 받은 미확정 결제가 캐시에 있어도 코치가 안내하지 않는다.
      await act(async () => {
        client.setQueryData(transactionKeys.pending(), {
          pages: [toPendingTransactions(pendingTransactionsMock())], pageParams: [null],
        });
      });
      await screen.findByLabelText(ROOM_LABEL);
      await layoutRoom();
    }

    it.each([
      { name: "미확정 결제", stickerCount: 0, overEnvelopes: [] },
      { name: "압류 딱지", stickerCount: 1, overEnvelopes: [] },
      { name: "어질러진 식탁", stickerCount: 0, overEnvelopes: [1] },
      { name: "미확정 결제·딱지·어질러짐", stickerCount: 1, overEnvelopes: [1] },
    ])("$name 상태만 있으면 말풍선과 아이콘을 만들지 않는다", async ({ stickerCount, overEnvelopes }) => {
      mockedGetRoom.mockResolvedValue(toRoom({
        ...roomMock, attendance: { checkedToday: true },
        stickers: { count: stickerCount, total: stickerCount, removableToday: true }, overEnvelopes,
      }));
      await showHome();

      expectNoSpeech();
      expect(mockedGetPending).not.toHaveBeenCalled();
      expect(useCoachSpeechStore.getState().latest).toBeNull();
      // 방 데이터는 그대로 남아 딱지와 어질러짐 렌더링에 전달된다.
      expect(client.getQueryData<Room>(roomKeys.home())).toMatchObject({
        stickers: { count: stickerCount }, overEnvelopeIds: overEnvelopes,
      });
      await setHomeFocused(false);
      await setHomeFocused(true);
      expectNoSpeech();
    });

    it("식비 초과 상태에서도 AI가 도착할 때만 표시하고 X로 닫으면 아이콘도 사라진다", async () => {
      await showHome();
      expectNoSpeech();

      await act(async () => { useCoachSpeechStore.getState().announce(feedback); });
      expect(screen.getByText(feedback)).toBeTruthy();
      expect(mockRoomLock).toHaveBeenLastCalledWith(true);
      await fireEvent.press(close());

      expectNoSpeech();
      expect(useCoachSpeechStore.getState().latest).toBeNull();
      expect(mockRoomLock).toHaveBeenLastCalledWith(false);
      await setHomeFocused(false);
      await setHomeFocused(true);
      expectNoSpeech();
      expect(mockPush).not.toHaveBeenCalled();
    });

    it("자동 접힘 뒤 직접 연 AI는 유지하고 본문·스크롤·X는 화면을 이동하지 않는다", async () => {
      useCoachSpeechStore.getState().announce(feedback);
      await showHome();
      await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS); });
      expect(screen.queryByText(feedback)).toBeNull();
      expect(mockRoomLock).toHaveBeenLastCalledWith(false);

      await fireEvent.press(icon());
      await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS * 4); });
      await fireEvent.press(screen.getByText(feedback));
      await fireEvent.scroll(screen.getByTestId("coach-speech-content"), { nativeEvent: { contentOffset: { x: 0, y: 10 } } });
      expect(screen.getByText(feedback)).toBeTruthy();
      expect(mockRoomLock).toHaveBeenLastCalledWith(true);
      await fireEvent.press(close());

      expectNoSpeech();
      expect(mockRoomLock).toHaveBeenLastCalledWith(false);
      expect(mockPush).not.toHaveBeenCalled();
    });

    it("A를 닫으면 새 AI B만 아이콘으로 남고 B를 닫은 뒤 일반 안내가 나타나지 않는다", async () => {
      useCoachSpeechStore.getState().announce(feedback);
      await showHome();
      const next = "다음 주에는 집밥 횟수를 늘려 보세요.";
      await act(async () => { useCoachSpeechStore.getState().announce(next); });
      expect(screen.getByText(feedback)).toBeTruthy();
      expect(screen.queryByText(next)).toBeNull();

      await fireEvent.press(close());
      expect(screen.queryByTestId("coach-speech-bubble")).toBeNull();
      expect(icon()).toBeTruthy();
      expect(useCoachSpeechStore.getState().latest?.text).toBe(next);
      await fireEvent.press(icon());
      expect(screen.getByText(next)).toBeTruthy();
      await fireEvent.press(close());

      expectNoSpeech();
      expect(useCoachSpeechStore.getState().latest).toBeNull();
    });
  });

  it("입주 연출에서 넘어오면 방을 다 그릴 때까지 입주 문구를 이어서 보여 준다", async () => {
    let resolveRoom: (room: ReturnType<typeof toRoom>) => void = () => undefined;
    mockedGetRoom.mockReturnValue(new Promise((resolve) => (resolveRoom = resolve)));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome({ arriving: true });

    expect(screen.getByRole("header", { name: "캐릭터가 입주하고 있어요" })).toBeTruthy();

    await act(async () => resolveRoom(toRoom({ ...roomMock, attendance: { checkedToday: true } })));
    expect(await screen.findByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(screen.queryByText("캐릭터가 입주하고 있어요")).toBeNull();
  });

  it("이미 입주한 계정은 방을 기다리는 동안 입주 문구 대신 다른 문구를 본다", async () => {
    let resolveRoom: (room: ReturnType<typeof toRoom>) => void = () => undefined;
    mockedGetRoom.mockReturnValue(new Promise((resolve) => (resolveRoom = resolve)));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();

    expect(screen.queryByText("캐릭터가 입주하고 있어요")).toBeNull();
    expect(screen.getByText(/^캐릭터가 .+ 있어요$/)).toBeTruthy();

    await act(async () => resolveRoom(toRoom({ ...roomMock, attendance: { checkedToday: true } })));
    expect(await screen.findByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(screen.queryByText(/^캐릭터가 .+ 있어요$/)).toBeNull();
  });

  it("방 정보를 못 받으면 대기 화면을 걷고 다시 시도를 보여 준다", async () => {
    mockedGetRoom.mockRejectedValue(new Error("network"));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();

    expect(await screen.findByText("방 정보를 불러오지 못했어요")).toBeTruthy();
    expect(screen.queryByLabelText("불러오는 중")).toBeNull();
  });

  it("불러오는 동안 대기 화면을 보여주고, 코인·알림·방을 표시하며 예산 카드는 리스트를 탭한 시트에 있다", async () => {
    let resolveRoom: (room: ReturnType<typeof toRoom>) => void = () => undefined;
    mockedGetRoom.mockReturnValue(new Promise((resolve) => (resolveRoom = resolve)));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    expect(screen.getByLabelText("불러오는 중")).toBeTruthy();

    await act(async () => resolveRoom(toRoom({ ...roomMock, attendance: { checkedToday: true } })));
    expect(await screen.findByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(screen.getByLabelText("코인 1,250개")).toBeTruthy();
    expect(screen.getByRole("button", { name: "알림" })).toBeTruthy();
    expect(screen.getByLabelText("캐릭터가 방에 있어요")).toBeTruthy();
    expect(screen.queryByText("남은 예산")).toBeNull();

    await layoutRoom();
    await fireEvent.press(await screen.findByRole("button", { name: "예산 보드, 9월 1일~30일 36% 남음" }));
    expect(await screen.findByText("180,000원")).toBeTruthy();
    expect(screen.getByText("남은 예산")).toBeTruthy();
    expect(screen.getByText(PERIOD)).toBeTruthy();
    expect(screen.getByText("총 예산 500,000원 중 320,000원 사용")).toBeTruthy();
    expect(screen.getByText("좋아요!")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "예산 사용률" }).props.accessibilityValue).toEqual({
      min: 0,
      max: 100,
      now: 64,
    });
    expect(mockedGetBudget).toHaveBeenCalledWith(expect.anything());
    expect(screen.queryByLabelText("불러오는 중")).toBeNull();
  });

  it("오늘 출석 전이면 홈 진입 시 출석을 한 번 처리하고 코인 배지와 토스트를 갱신한다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom(roomMock));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();

    expect(await screen.findByLabelText("출석 +10 코인")).toBeTruthy();
    expect(screen.getByLabelText("코인 1,260개")).toBeTruthy();
    await waitFor(() => expect(mockedCheckAttendance).toHaveBeenCalledTimes(1));
  });

  it("오늘 이미 출석했으면 출석을 부르지 않는다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();

    expect(await screen.findByLabelText("코인 1,250개")).toBeTruthy();
    expect(await screen.findByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(mockedCheckAttendance).not.toHaveBeenCalled();
  });

  it("지급 코인이 0이면 토스트 없이 잔액만 반영한다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom(roomMock));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    mockedCheckAttendance.mockResolvedValue(toAttendance({ granted: 0, balance: 1250 }));
    await renderHome();

    expect(await screen.findByLabelText("코인 1,250개")).toBeTruthy();
    await waitFor(() => expect(mockedCheckAttendance).toHaveBeenCalledTimes(1));
    expect(await screen.findByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(screen.queryByLabelText(/출석 \+/)).toBeNull();
  });

  it("예산 시트의 카드에 봉투 7종 사용률 막대를 그리고 초과 봉투는 사용률이 100 을 넘는다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    await layoutRoom();
    await fireEvent.press(await screen.findByRole("button", { name: "예산 보드, 9월 1일~30일 36% 남음" }));

    expect(await screen.findByText("봉투별 사용률")).toBeTruthy();
    expect(screen.getByLabelText("외식 사용률 68%, 남은 32,000원")).toBeTruthy();
    expect(screen.getByLabelText("쇼핑 사용률 109%, 남은 -8,000원")).toBeTruthy();
    expect(screen.getByText("마트")).toBeTruthy();
  });

  it("벽 리스트 에셋은 잔여율을 읽어 주고, 탭하면 예산 시트가 열리며 링크는 예산 탭으로 간다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    const board = await screen.findByRole("button", { name: "예산 보드, 9월 1일~30일 36% 남음" });
    expect(screen.queryByText("봉투별 남은 금액")).toBeNull();

    await fireEvent.press(board);
    expect(await screen.findByText("봉투별 남은 금액")).toBeTruthy();
    expect(screen.getByText("9월 1일~30일")).toBeTruthy();
    expect(screen.getByLabelText("쇼핑 초과 8,000원 남음")).toBeTruthy();
    expect(screen.getByLabelText("외식 32,000원 남음")).toBeTruthy();

    await fireEvent.press(screen.getByRole("button", { name: "보드 닫기" }));
    expect(screen.queryByText("봉투별 남은 금액")).toBeNull();

    // 링크로 나가면 시트도 닫힌다 — 돌아왔을 때 시트가 열린 채 남지 않도록.
    await fireEvent.press(board);
    await fireEvent.press(await screen.findByRole("button", { name: "예산 탭에서 자세히" }));
    expect(mockPush).toHaveBeenCalledWith("/budget");
    expect(screen.queryByText("봉투별 남은 금액")).toBeNull();
    await waitForQueriesToSettle();
  });

  it("이번 주기 예산이 확정 전(PROPOSED)이면 홈 대신 예산 확정 화면으로 보낸다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetProposedMock(TODAY_KEY)));
    await renderHome();

    await waitFor(() => expect(mockRedirect).toHaveBeenCalledWith(PROPOSAL_FROM_HOME_HREF));
    expect(screen.queryByText("남은 예산")).toBeNull();
    expect(screen.queryByRole("button", { name: /예산 보드/ })).toBeNull();
    await waitForQueriesToSettle();
  });

  it("캘린더 에셋은 다음 출금을 보여주고, 탭하면 결제 캘린더 화면으로 바로 간다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    const calendar = await screen.findByRole("button", { name: "출금 캘린더, 9월 15일 월세, 준비 부족" });
    expect(mockedGetCalendar).toHaveBeenCalledWith(MONTH, expect.anything());

    await fireEvent.press(calendar);
    expect(mockPush).toHaveBeenCalledWith("/payment/calendar");
    // 중간 팝오버를 거치지 않는다 (사용자 결정 2026-09-18)
    expect(screen.queryByText("9월 출금 일정")).toBeNull();
    await waitForQueriesToSettle();
  });

  it("이번 달 출금 예정이 없어도 캘린더 에셋은 보이고, 탭하면 그대로 결제 캘린더로 간다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    mockedGetCalendar.mockResolvedValue(toPaymentCalendar(paymentCalendarEmptyMock));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    await fireEvent.press(await screen.findByRole("button", { name: "출금 캘린더, 9월 출금 예정 없음" }));
    expect(mockPush).toHaveBeenCalledWith("/payment/calendar");
    expect(screen.queryByText("이번 달 출금 예정이 없어요.")).toBeNull();
    await waitForQueriesToSettle();
  });

  it("예산 보드는 시트로 열리고, 캘린더는 시트 대신 결제 캘린더 화면으로 간다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    await fireEvent.press(await screen.findByRole("button", { name: "예산 보드, 9월 1일~30일 36% 남음" }));
    expect(await screen.findByText("봉투별 남은 금액")).toBeTruthy();

    await fireEvent.press(screen.getByRole("button", { name: "출금 캘린더, 9월 15일 월세, 준비 부족" }));
    expect(mockPush).toHaveBeenCalledWith("/payment/calendar");
    expect(screen.queryByText("9월 출금 일정")).toBeNull();
    await waitForQueriesToSettle();
  });

  it("결제 일정만 못 받으면 캘린더 에셋만 감추고 나머지는 그대로 둔다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    mockedGetCalendar.mockRejectedValue(new Error("network"));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();

    expect(await screen.findByRole("button", { name: "예산 보드, 9월 1일~30일 36% 남음" })).toBeTruthy();
    expect(screen.queryByLabelText(/출금 캘린더/)).toBeNull();
    await waitForQueriesToSettle();
  });

  it("확정 전 예산이면 방 정보를 기다리지 않고 확정 화면으로 보낸다(홈으로 돌아오도록 next=home)", async () => {
    mockedGetRoom.mockReturnValue(new Promise(() => undefined));
    mockedGetBudget.mockResolvedValue(toBudget(budgetProposedMock(TODAY_KEY)));
    await renderHome();

    await waitFor(() => expect(mockRedirect).toHaveBeenCalledWith({ pathname: "/onboarding/budget-proposal", params: { next: "home" } }));
  });

  it("방 정보를 못 받으면 화면 전체에 오류와 재시도를 보여주고, 재시도 성공 시 내용을 표시한다", async () => {
    mockedGetRoom.mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(toRoom(roomMock));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();

    expect(await screen.findByText("방 정보를 불러오지 못했어요")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "다시 시도" }));

    expect(await screen.findByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(mockedGetRoom).toHaveBeenCalledTimes(2);
  });

  it("방 재조회 중·실패에도 씬을 유지하고 앱 복귀 후 최신 데이터로 회복한다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, attendance: { checkedToday: true } }));
    mockedGetBudget.mockResolvedValue(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();
    await screen.findByLabelText(ROOM_LABEL);
    await layoutRoom();
    expect(mockSceneMount).toHaveBeenCalledTimes(1);

    let rejectRefresh!: (error: Error) => void;
    mockedGetRoom.mockImplementationOnce(() => new Promise<Room>((_resolve, reject) => { rejectRefresh = reject; }));
    await act(async () => { void client.invalidateQueries({ queryKey: roomKeys.home() }); });
    expect(screen.getByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(screen.getByRole("button", { name: HOME_HELP_LABEL })).toBeTruthy();
    await act(async () => rejectRefresh(new Error("network")));
    await waitFor(() => expect(client.getQueryState(roomKeys.home())?.status).toBe("error"));
    expect(screen.getByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(screen.getByRole("button", { name: HOME_HELP_LABEL })).toBeTruthy();
    expect(screen.queryByText("방 정보를 불러오지 못했어요")).toBeNull();
    expect(mockSceneUnmount).not.toHaveBeenCalled();

    mockedGetRoom.mockResolvedValue(toRoom({ ...roomMock, coin: { balance: 999 }, attendance: { checkedToday: true } }));
    await act(async () => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });
    expect(await screen.findByRole("button", { name: "코인 999개" })).toBeTruthy();
    expect(mockSceneMount).toHaveBeenCalledTimes(1);
    expect(mockSceneUnmount).not.toHaveBeenCalled();
    expect(mockedGetRoom).toHaveBeenCalledTimes(3);
    focusManager.setFocused(undefined);
    await waitForQueriesToSettle();
  });

  it("예산만 못 받으면 방은 그대로 두고, 리스트를 탭한 시트 안에서 재시도한다", async () => {
    mockedGetRoom.mockResolvedValue(toRoom(roomMock));
    mockedGetBudget.mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(toBudget(budgetConfirmedMock(TODAY_KEY)));
    await renderHome();

    expect(await screen.findByLabelText(ROOM_LABEL)).toBeTruthy();
    expect(screen.getByLabelText("캐릭터가 방에 있어요")).toBeTruthy();
    await layoutRoom();
    await fireEvent.press(await screen.findByRole("button", { name: "예산 보드, 불러오지 못했어요" }));
    expect(await screen.findByText("예산을 불러오지 못했어요")).toBeTruthy();

    await fireEvent.press(screen.getByRole("button", { name: "다시 시도" }));
    expect(await screen.findByText("180,000원")).toBeTruthy();
    expect(mockedGetBudget).toHaveBeenCalledTimes(2);
  });
});
