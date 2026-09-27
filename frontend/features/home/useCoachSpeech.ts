import * as React from "react";

import type { CoachSpeech } from "@/features/notification/store";

/** 말풍선을 펼쳐 두는 시간. 2~3초 보여 준 뒤 대화 아이콘으로 접는다 (사용자 요청 2026-09-23) */
export const COACH_SPEECH_OPEN_MS = 2500;

export type CoachSpeechView = {
  /** 말풍선에 보일 문장. 펼쳐 있는 동안은 펼친 순간의 문장을 유지한다 */
  text: string;
  /** true 면 말풍선, false 면 접힌 대화 아이콘 */
  open: boolean;
  /** 아직 한 번도 직접 열어 보지 않았으면 아이콘에 빨간 점을 단다 */
  unread: boolean;
  onPressIcon: () => void;
  onClose: () => void;
};

/**
 * 코치 고양이 말풍선의 펼침·접힘 (사용자 요청 2026-09-23).
 * 처음 보는 문장이 생기면 말풍선을 COACH_SPEECH_OPEN_MS 동안 펼쳤다가 대화 아이콘으로 접는다. 아이콘을 누르면 다시 펼치고 읽음으로 친다.
 * 아이콘으로 직접 연 말풍선은 저절로 접지 않고 X로 닫는다 — 긴 코치 피드백을 끝까지 읽게 (-184, 사용자 결정 2026-09-24).
 * paused(방 대기 화면·안내·보드·딱지 창이 떠 있는 동안)에는 가리고, 끝나면 못 보여 준 문장을 다시 펼친다.
 * inactive(홈 밖·앱 백그라운드)에서는 펼침만 해제한다. 읽음이나 자동 표시 기록은 유지하고, 복귀 후에는 새 문장만 펼친다.
 * onRead 는 AI 코칭을 직접 열거나 X로 닫을 때 부른다. 저장소에서 지워져도 이미 펼친 본문은 닫을 때까지 유지한다.
 */
export function useCoachSpeech(
  message: CoachSpeech | null,
  { paused, active }: { paused: boolean; active: boolean },
  onRead: (key: string) => void,
): CoachSpeechView | null {
  const [opened, setOpened] = React.useState<CoachSpeech | null>(null);
  /** 자동 표시를 마쳤거나 X로 닫으며 아이콘에 남긴 문장. 읽음 기록과는 별개다 */
  const [seenKeys, setSeenKeys] = React.useState<readonly string[]>([]);
  const [readKeys, setReadKeys] = React.useState<readonly string[]>([]);
  /** 아이콘으로 직접 연 말풍선의 key. 이 말풍선은 시간이 지나도 접지 않는다 */
  const [pinnedKey, setPinnedKey] = React.useState<string | null>(null);
  /** 오버레이에 가려져 다시 보여 줄 미읽음 문장. 홈을 떠나면 재표시 예약만 취소한다 */
  const [resumeKey, setResumeKey] = React.useState<string | null>(null);
  /** X로 닫을 때 도착해 있던 다음 AI 코칭은 다음 렌더에서 자동으로 펼치지 않고 아이콘으로 남긴다 */
  const [closing, setClosing] = React.useState(false);

  if (closing) {
    setClosing(false);
    if (message !== null && !seenKeys.includes(message.key)) setSeenKeys([...seenKeys, message.key]);
  }

  // 화면 이탈은 오버레이 가림보다 우선한다. onRead는 호출하지 않아 미읽음 AI 코칭을 지우지 않는다.
  if (!active) {
    if (opened !== null) setOpened(null);
    if (pinnedKey !== null) setPinnedKey(null);
    if (resumeKey !== null) setResumeKey(null);
  } else if (paused) {
    if (opened !== null) {
      setOpened(null);
      setPinnedKey(null);
      if (!readKeys.includes(opened.key)) setResumeKey(opened.key);
    }
  } else {
    // 처음 보는 문장 또는 오버레이에 가려졌던 문장만 자동 표시한다. 다른 문장이 펼쳐 있으면 그 스냅샷을 유지한다.
    if (message !== null && opened === null && !closing && (!seenKeys.includes(message.key) || resumeKey === message.key)) {
      if (!seenKeys.includes(message.key)) setSeenKeys([...seenKeys, message.key]);
      setOpened(message);
    }
    if (resumeKey !== null) setResumeKey(null);
  }

  // 펼친 말풍선은 정해진 시간 뒤 접는다 — 시계라는 외부 시스템에 맞추는 일이라 effect 로 둔다
  const openedKey = opened?.key ?? null;
  const pinned = openedKey !== null && openedKey === pinnedKey;
  React.useEffect(() => {
    if (!active || paused || openedKey === null || pinned) return;
    const timer = setTimeout(() => setOpened((current) => (current?.key === openedKey ? null : current)), COACH_SPEECH_OPEN_MS);
    return () => clearTimeout(timer);
  }, [active, paused, openedKey, pinned]);

  const read = (key: string) => {
    if (!readKeys.includes(key)) setReadKeys([...readKeys, key]);
    onRead(key);
  };

  if (!active || paused || (message === null && opened === null)) return null;
  const shown = opened ?? message;
  if (shown === null) return null;

  return {
    text: shown.text,
    open: opened !== null,
    unread: message !== null && !readKeys.includes(message.key),
    onPressIcon: () => {
      if (message === null) return;
      read(message.key);
      setOpened(message);
      setPinnedKey(message.key);
    },
    onClose: () => {
      if (opened === null) return;
      setOpened(null);
      setPinnedKey(null);
      setClosing(true);
      read(opened.key);
    },
  };
}
