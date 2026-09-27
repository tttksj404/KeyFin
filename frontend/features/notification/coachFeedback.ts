import { getCoachFeedback } from "@/features/notification/api/notification.api";
import type { CoachFeedback } from "@/features/notification/model";
import { reportPushSkip } from "@/features/notification/push";
import { useCoachSpeechStore } from "@/features/notification/store";

/** 서버가 AI 평가를 받는 동안(PENDING) 다시 묻는 간격과 횟수 — 보통 수 초 안에 READY 가 된다 */
export const COACH_FEEDBACK_POLL_MS = 3_000;
export const COACH_FEEDBACK_MAX_ATTEMPTS = 10;

type Deps = {
  fetch: (notificationId: number) => Promise<CoachFeedback>;
  wait: (ms: number) => Promise<void>;
  announce: (text: string) => void;
};

const defaultDeps: Deps = {
  fetch: (notificationId) => getCoachFeedback(notificationId),
  wait: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  announce: (text) => useCoachSpeechStore.getState().announce(text),
};

/** 이번 실행에서 이미 물어본 알림. 푸시 수신·탭·알림함이 같은 알림으로 겹쳐 불러도 코치는 한 번만 말한다 */
const requested = new Set<number>();

/**
 * 예산 구간 알림의 코치 피드백을 받아 홈의 코치 고양이가 말하게 한다 (-184, 사용자 결정 2026-09-24).
 * PENDING 이면 잠시 뒤 다시 묻고, READY 면 문장을 말풍선 저장소에 넣는다. FAILED·NONE·시간 초과·오류는 말하지 않는다.
 * 화면 데이터가 아니라 한 번 말하고 끝나는 부수 효과라 Query 캐시에 두지 않는다.
 */
export async function announceCoachFeedback(notificationId: number, deps: Deps = defaultDeps): Promise<void> {
  if (requested.has(notificationId)) return;
  requested.add(notificationId);
  try {
    for (let attempt = 0; attempt < COACH_FEEDBACK_MAX_ATTEMPTS; attempt += 1) {
      const feedback = await deps.fetch(notificationId);
      if (feedback.status === "READY" && feedback.text !== null) {
        deps.announce(feedback.text);
        return;
      }
      if (feedback.status !== "PENDING") return;
      await deps.wait(COACH_FEEDBACK_POLL_MS);
    }
  } catch (error) {
    reportPushSkip("코치 피드백", error);
  }
}

/** 테스트 전용: 물어본 알림 기록을 비운다 */
export function resetCoachFeedbackRequests(): void {
  requested.clear();
}
