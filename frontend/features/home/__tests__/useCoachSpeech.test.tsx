import { act, renderHook } from "@testing-library/react-native";

import { COACH_SPEECH_OPEN_MS, useCoachSpeech } from "@/features/home/useCoachSpeech";
import { useCoachSpeechStore, type CoachSpeech } from "@/features/notification/store";

const feedback = { key: "feedback-a", text: "외식 예산을 넘었다냥. 이번 주기에는 외식을 멈추는 편이 좋다냥." };
const nextFeedback = { key: "feedback-b", text: "교통비도 확인해 봐요." };
const visible = { active: true, paused: false };

/** HomeScreen처럼 AI 코칭만 구독하고, 읽음 처리에서 동기 clear 한다. */
function useStoreSpeech(options: typeof visible, onRead: (key: string) => void) {
  const aiSpeech = useCoachSpeechStore((state) => state.latest);
  const clear = useCoachSpeechStore((state) => state.clear);
  return useCoachSpeech(aiSpeech, options, (key) => {
    onRead(key);
    clear(key);
  });
}

describe("useCoachSpeech — 말풍선 펼침·접힘", () => {
  let setTimeoutSpy: jest.SpyInstance;
  let clearTimeoutSpy: jest.SpyInstance;
  const speechTimers = () => setTimeoutSpy.mock.calls.flatMap(([, delay], index) =>
    delay === COACH_SPEECH_OPEN_MS ? [setTimeoutSpy.mock.results[index].value] : []);

  beforeEach(() => {
    jest.useFakeTimers();
    setTimeoutSpy = jest.spyOn(globalThis, "setTimeout");
    clearTimeoutSpy = jest.spyOn(globalThis, "clearTimeout");
    useCoachSpeechStore.setState({ latest: null });
  });
  afterEach(() => {
    jest.restoreAllMocks();
    jest.useRealTimers();
  });

  it("자동 말풍선은 2.5초 뒤 접히고, 아이콘으로 연 말풍선은 X로 닫을 때까지 남는다", async () => {
    const onRead = jest.fn();
    const hook = await renderHook(() => useCoachSpeech(feedback, visible, onRead));
    expect(hook.result.current?.open).toBe(true);

    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS); });
    expect(hook.result.current).toMatchObject({ open: false, unread: true });
    expect(onRead).not.toHaveBeenCalled();

    await act(async () => { hook.result.current?.onPressIcon(); });
    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS * 4); });
    expect(hook.result.current).toMatchObject({ open: true, unread: false });
    expect(onRead).toHaveBeenCalledWith(feedback.key);

    await act(async () => { hook.result.current?.onClose(); });
    expect(hook.result.current?.open).toBe(false);
  });

  it.each([false, true])("홈을 떠나면 펼침과 타이머만 해제하고 복귀 시 기존 문장을 다시 펼치지 않는다 (수동 열기: %s)", async (manual) => {
    const onRead = jest.fn();
    const hook = await renderHook((options: typeof visible) => useCoachSpeech(feedback, options, onRead), { initialProps: visible });
    if (manual) {
      await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS); });
      await act(async () => { hook.result.current?.onPressIcon(); });
    }
    const readCount = onRead.mock.calls.length;

    // 같은 렌더에서 overlay와 inactive가 함께 와도 화면 이탈을 우선한다.
    await hook.rerender({ active: false, paused: true });
    expect(hook.result.current).toBeNull();
    expect(speechTimers()).toHaveLength(1);
    expect(clearTimeoutSpy).toHaveBeenCalledWith(speechTimers()[0]);
    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS * 4); });
    await hook.rerender(visible);
    expect(hook.result.current).toMatchObject({ open: false, unread: !manual });
    expect(onRead).toHaveBeenCalledTimes(readCount);
  });

  it("오버레이에 가린 미읽음 문장은 복귀 후 온전히 2.5초 동안 다시 보여 준다", async () => {
    const hook = await renderHook((options: typeof visible) => useCoachSpeech(feedback, options, jest.fn()), { initialProps: visible });
    await act(async () => { jest.advanceTimersByTime(1_000); });
    await hook.rerender({ active: true, paused: true });
    expect(hook.result.current).toBeNull();
    expect(clearTimeoutSpy).toHaveBeenCalledWith(speechTimers()[0]);

    await hook.rerender(visible);
    expect(hook.result.current?.open).toBe(true);
    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS - 1); });
    expect(hook.result.current?.open).toBe(true);
    await act(async () => { jest.advanceTimersByTime(1); });
    expect(hook.result.current?.open).toBe(false);
  });

  it("오버레이에 가려진 뒤 홈을 떠나면 재표시 예약도 해제한다", async () => {
    const onRead = jest.fn();
    const hook = await renderHook((options: typeof visible) => useCoachSpeech(feedback, options, onRead), { initialProps: visible });
    await hook.rerender({ active: true, paused: true });
    await hook.rerender({ active: false, paused: true });
    await hook.rerender(visible);
    expect(hook.result.current).toMatchObject({ open: false, unread: true });
    expect(onRead).not.toHaveBeenCalled();
  });

  it("홈 밖에서 도착한 새 문장은 타이머 없이 기다리다가 복귀 후 자동 표시한다", async () => {
    const onRead = jest.fn();
    const initialProps: { message: CoachSpeech | null; active: boolean } = { message: feedback, active: true };
    const hook = await renderHook(({ message, active }: typeof initialProps) => useCoachSpeech(message, { active, paused: false }, onRead), { initialProps });
    await hook.rerender({ message: feedback, active: false });
    await hook.rerender({ message: nextFeedback, active: false });
    expect(hook.result.current).toBeNull();
    expect(speechTimers()).toHaveLength(1);
    expect(clearTimeoutSpy).toHaveBeenCalledWith(speechTimers()[0]);

    await hook.rerender({ message: nextFeedback, active: true });
    expect(hook.result.current).toMatchObject({ text: nextFeedback.text, open: true, unread: true });
    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS); });
    expect(hook.result.current?.open).toBe(false);
    expect(onRead).not.toHaveBeenCalled();
  });

  it("새 문장이 도착해도 현재 문장의 타이머는 유지하고 자동 접힘 뒤 새 문장을 온전히 표시한다", async () => {
    const onRead = jest.fn();
    const hook = await renderHook((message: CoachSpeech) => useCoachSpeech(message, visible, onRead), { initialProps: feedback });
    await act(async () => { jest.advanceTimersByTime(1_000); });
    await hook.rerender(nextFeedback);
    expect(hook.result.current).toMatchObject({ text: feedback.text, open: true });

    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS - 1_000); });
    expect(hook.result.current).toMatchObject({ text: nextFeedback.text, open: true });
    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS - 1); });
    expect(hook.result.current?.open).toBe(true);
    await act(async () => { jest.advanceTimersByTime(1); });
    expect(hook.result.current?.open).toBe(false);
    expect(onRead).not.toHaveBeenCalled();
  });

  it("X로 AI 코칭을 지우면 아이콘도 없애고 이후 새 코칭은 자동 표시한다", async () => {
    useCoachSpeechStore.setState({ latest: feedback });
    const onRead = jest.fn();
    const hook = await renderHook(() => useStoreSpeech(visible, onRead));

    await act(async () => { hook.result.current?.onClose(); });
    expect(useCoachSpeechStore.getState().latest).toBeNull();
    expect(hook.result.current).toBeNull();
    expect(onRead.mock.calls).toEqual([[feedback.key]]);
    expect(speechTimers()).toHaveLength(1);
    expect(clearTimeoutSpy).toHaveBeenCalledWith(speechTimers()[0]);

    await act(async () => { useCoachSpeechStore.getState().announce(nextFeedback.text); });
    expect(hook.result.current).toMatchObject({ text: nextFeedback.text, open: true, unread: true });
  });

  it("A를 보는 중 도착한 B는 A를 바꾸지 않고, X는 A만 읽어 B를 미읽음 아이콘으로 남긴다", async () => {
    useCoachSpeechStore.setState({ latest: feedback });
    const onRead = jest.fn();
    const hook = await renderHook(() => useStoreSpeech(visible, onRead));
    await act(async () => { useCoachSpeechStore.setState({ latest: nextFeedback }); });
    expect(hook.result.current).toMatchObject({ text: feedback.text, open: true });

    await act(async () => { hook.result.current?.onClose(); });
    expect(useCoachSpeechStore.getState().latest).toEqual(nextFeedback);
    expect(hook.result.current).toMatchObject({ text: nextFeedback.text, open: false, unread: true });
    expect(onRead.mock.calls).toEqual([[feedback.key]]);

    // B를 직접 읽으면 저장소는 비워지지만 열린 B 스냅샷은 유지된다.
    await act(async () => { hook.result.current?.onPressIcon(); });
    expect(useCoachSpeechStore.getState().latest).toBeNull();
    expect(hook.result.current).toMatchObject({ text: nextFeedback.text, open: true });
    await act(async () => { jest.advanceTimersByTime(COACH_SPEECH_OPEN_MS * 4); });
    expect(hook.result.current?.open).toBe(true);
    await act(async () => { hook.result.current?.onClose(); });
    expect(hook.result.current).toBeNull();
  });

  it("홈을 떠나도 미읽음 AI 코칭은 읽거나 삭제하지 않는다", async () => {
    useCoachSpeechStore.setState({ latest: feedback });
    const onRead = jest.fn();
    const hook = await renderHook((options: typeof visible) => useStoreSpeech(options, onRead), { initialProps: visible });
    await hook.rerender({ active: false, paused: false });
    expect(useCoachSpeechStore.getState().latest).toEqual(feedback);
    expect(onRead).not.toHaveBeenCalled();
    await hook.rerender(visible);
    expect(hook.result.current).toMatchObject({ text: feedback.text, open: false, unread: true });
  });
});
