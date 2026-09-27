import type { CoachPersona, NotificationKind } from "@/features/settings/model";

/** 알림 종류 이름과 설명. 종류 값은 계약이고 문구는 클라이언트 상수다 (PAGE-27, Pencil 시안 없음) */
const NOTIFICATION_LABELS: Record<NotificationKind, { title: string; description: string }> = {
  coaching: { title: "코치 한마디", description: "소비 습관에 대한 코치 멘트를 보내요." },
  budgetAlert: { title: "예산 잔액", description: "봉투 잔액이 줄어드는 구간마다 알려 줘요." },
  transfer: { title: "이체 승인 요청", description: "결제일 전에 옮길 금액을 승인해 달라고 알려 줘요." },
  cleanup: { title: "정리할 결제", description: "분류하지 못한 결제가 쌓이면 알려 줘요." },
};

export function notificationLabel(kind: NotificationKind): { title: string; description: string } {
  return NOTIFICATION_LABELS[kind];
}

/** 코치 말투 이름. 캐릭터 이름 3종은 docs/api-contract.md 의 CoachPersona 를 따르고, PLAIN 은 말투를 쓰지 않는 값이다 */
const COACH_PERSONA_LABELS: Record<CoachPersona, string> = {
  PLAIN: "말투 없음",
  DODO: "도도냥",
  ONSOON: "온순냥",
  JIBANG: "지방냥",
  UNKNOWN: "알 수 없음",
};

export function coachPersonaLabel(persona: CoachPersona): string {
  return COACH_PERSONA_LABELS[persona];
}

/** 방해 금지 시각 후보. 30분 간격 48개 ("00:00" ~ "23:30") */
export const QUIET_HOUR_OPTIONS: readonly string[] = Array.from({ length: 48 }, (_, index) => {
  const hour = String(Math.floor(index / 2)).padStart(2, "0");
  return `${hour}:${index % 2 === 0 ? "00" : "30"}`;
});
