import { create } from "zustand";

/**
 * AI 피드백 API에서 받은 코칭을 홈의 고양이 말풍선에 보여 주는 상태.
 * 조회 진입점(푸시 수신·탭·알림함)과 홈 화면이 달라 전역으로 두며, 최신 AI 코칭 하나만 담는다.
 * key 는 같은 문장이 다른 알림에서 다시 와도 새 코칭으로 알아보게 하는 순번이다.
 */
export type CoachSpeech = { key: string; text: string };

type CoachSpeechState = {
  latest: CoachSpeech | null;
  announce: (text: string) => void;
  /** 사용자가 읽은 AI 코칭을 치운다. 그 사이 새 코칭이 왔으면 새 것은 남긴다 */
  clear: (key: string) => void;
};

let sequence = 0;

export const useCoachSpeechStore = create<CoachSpeechState>((set) => ({
  latest: null,
  announce: (text) => {
    sequence += 1;
    set({ latest: { key: `coach-${sequence}`, text } });
  },
  clear: (key) => set((state) => (state.latest?.key === key ? { latest: null } : state)),
}));
