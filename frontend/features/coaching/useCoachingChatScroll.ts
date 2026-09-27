import { useFocusEffect } from "expo-router";
import * as React from "react";
import { Keyboard, Platform, type FlatList, type LayoutChangeEvent, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";

type KeyboardOpening = { height: number; offset: number };

/** 최초 진입(0)·전송 시도의 하단 이동과, 키패드가 가린 높이의 위치 보정을 따로 관리한다. */
export function useCoachingChatScroll<ItemT>(
  listRef: React.RefObject<FlatList<ItemT> | null>,
  requestId: number,
  enabled: boolean
) {
  const contentHeight = React.useRef<number | null>(null);
  const viewportHeight = React.useRef(0);
  const laidOutRequest = React.useRef<number | null>(null);
  const pendingRequest = React.useRef<number | null>(null);
  const startedRequest = React.useRef<number | null>(null);
  const finishedRequest = React.useRef<number | null>(null);
  const frame = React.useRef<number | null>(null);
  const offset = React.useRef(0);
  const active = React.useRef(true);
  const keyboard = React.useRef({
    visible: false,
    opening: null as KeyboardOpening | null,
    pending: false,
    cancelled: false,
  });
  const keyboardFrame = React.useRef<number | null>(null);

  const clearFrame = React.useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
  }, []);

  // 응답은 하단 이동만 취소한다. 같은 시점에 열린 키패드의 위치 보정은 독립적이다.
  const cancelRequest = React.useCallback(() => {
    if (startedRequest.current !== null) finishedRequest.current = startedRequest.current;
    pendingRequest.current = null;
    clearFrame();
  }, [clearFrame]);

  const cancelKeyboard = React.useCallback(() => {
    if (keyboardFrame.current !== null) cancelAnimationFrame(keyboardFrame.current);
    keyboardFrame.current = null;
    if (keyboard.current.opening !== null || keyboard.current.visible) keyboard.current.cancelled = true;
    keyboard.current.opening = null;
    keyboard.current.pending = false;
  }, []);

  const cancel = React.useCallback(() => {
    cancelRequest();
    cancelKeyboard();
  }, [cancelKeyboard, cancelRequest]);

  const scheduleKeyboard = React.useCallback(() => {
    if (keyboardFrame.current !== null) cancelAnimationFrame(keyboardFrame.current);
    keyboardFrame.current = null;
    const opening = keyboard.current.opening;
    if (!active.current || !keyboard.current.pending || opening === null || pendingRequest.current !== null
      || contentHeight.current === null || viewportHeight.current <= 0 || viewportHeight.current >= opening.height) return;

    keyboardFrame.current = requestAnimationFrame(() => {
      keyboardFrame.current = null;
      if (!active.current || !keyboard.current.pending || keyboard.current.opening !== opening || listRef.current === null) return;
      keyboard.current.pending = false;
      keyboard.current.opening = null;
      const maxOffset = Math.max(0, (contentHeight.current ?? 0) - viewportHeight.current);
      offset.current = Math.min(maxOffset, Math.max(0, opening.offset + opening.height - viewportHeight.current));
      listRef.current.scrollToOffset({ offset: offset.current, animated: false });
    });
  }, [listRef]);

  const schedule = React.useCallback(() => {
    clearFrame();
    const id = pendingRequest.current;
    if (!active.current || id === null || laidOutRequest.current !== id || contentHeight.current === null || viewportHeight.current <= 0) return;

    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      if (pendingRequest.current !== id || listRef.current === null) return;
      pendingRequest.current = null;
      finishedRequest.current = id;
      offset.current = Math.max(0, (contentHeight.current ?? 0) - viewportHeight.current);
      listRef.current.scrollToOffset({
        offset: offset.current,
        animated: false,
      });
    });
  }, [clearFrame, listRef]);

  React.useLayoutEffect(() => {
    if (!enabled) {
      cancelRequest();
      return;
    }
    if (finishedRequest.current !== requestId) {
      // 최초 진입·전송·재시도의 하단 이동이 같은 키패드 열기보다 우선한다.
      cancelKeyboard();
      startedRequest.current = requestId;
      pendingRequest.current = requestId;
      schedule();
    }
    // 언마운트와 요청 변경 시 예약만 폐기한다. StrictMode의 effect 재실행은 아직 완료하지 않은 요청을 이어 간다.
    return () => {
      pendingRequest.current = null;
      clearFrame();
    };
  }, [cancelKeyboard, cancelRequest, clearFrame, enabled, requestId, schedule]);

  useFocusEffect(React.useCallback(() => {
    active.current = true;
    schedule();
    keyboard.current = { visible: Platform.OS !== "web" && Keyboard.isVisible(), opening: null, pending: false, cancelled: false };
    const subscriptions = Platform.OS === "web" ? [] : [
      Keyboard.addListener(Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow", () => {
        if (!active.current || keyboard.current.visible) return;
        keyboard.current.visible = true;
        if (keyboard.current.cancelled || pendingRequest.current !== null) {
          cancelKeyboard();
          return;
        }
        keyboard.current.opening ??= { height: viewportHeight.current, offset: offset.current };
        keyboard.current.pending = true;
        scheduleKeyboard();
      }),
      Keyboard.addListener(Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide", () => {
        cancelKeyboard();
        keyboard.current = { visible: false, opening: null, pending: false, cancelled: false };
      }),
    ];
    return () => {
      active.current = false;
      // StrictMode 재실행에서는 layout effect가 먼저 예약을 비운다. 그 요청까지 완료 처리하지 않는다.
      if (pendingRequest.current !== null) cancelRequest();
      clearFrame();
      cancelKeyboard();
      subscriptions.forEach((subscription) => subscription.remove());
    };
  }, [cancelKeyboard, cancelRequest, clearFrame, schedule, scheduleKeyboard]));

  // Android에서 목록 배치가 didShow보다 먼저 바뀌어도 열기 전 기준을 잃지 않는다.
  // 포커스를 유지한 채 시스템 뒤로 가기로 키패드를 닫았다 다시 누르는 경우도 기록한다.
  const onInputFocus = React.useCallback(() => {
    if (!active.current || Platform.OS === "web" || keyboard.current.visible) return;
    keyboard.current.opening ??= { height: viewportHeight.current, offset: offset.current };
    keyboard.current.cancelled = false;
  }, []);

  const onScroll = React.useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
    offset.current = Math.max(0, event.nativeEvent.contentOffset.y);
  }, []);

  const onContentSizeChange = React.useCallback((_width: number, height: number) => {
    contentHeight.current = height;
    schedule();
    scheduleKeyboard();
  }, [schedule, scheduleKeyboard]);

  const onLayout = React.useCallback((event: LayoutChangeEvent) => {
    viewportHeight.current = event.nativeEvent.layout.height;
    schedule();
    scheduleKeyboard();
  }, [schedule, scheduleKeyboard]);

  // 요청마다 footer를 새로 배치한다. 높이가 같은 재시도도 새 렌더가 네이티브에 반영된 뒤 이동한다.
  const onRequestLayout = React.useCallback(() => {
    laidOutRequest.current = requestId;
    schedule();
  }, [requestId, schedule]);

  return { cancel, cancelRequest, onContentSizeChange, onLayout, onRequestLayout, onScroll, onInputFocus };
}
