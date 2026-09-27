import type { CoachPersonaDto, NotificationSettingsDto, TransferSettingsDto } from "@/features/settings/model";

/**
 * GET/PUT /settings/transfer 응답 예시 (docs/api-contract.md USER).
 * 서버처럼 상태를 들고 있어야 저장한 값이 다시 조회될 때 보인다.
 */
const INITIAL: TransferSettingsDto = { transferConsent: true, transferLimitOnce: 500000, transferLimitDaily: 1000000 };

let settings: TransferSettingsDto = { ...INITIAL };

export function transferSettingsMock(): TransferSettingsDto {
  return { ...settings };
}

export function updateTransferSettingsMock(request: TransferSettingsDto): TransferSettingsDto {
  settings = { ...request };
  return { ...settings };
}

/**
 * GET /settings/notifications · /settings/coach 응답 예시 (배포 서버 Swagger 2026-09-20).
 * 값은 Swagger 예시 그대로이며 방해 금지는 자정을 지나는 범위다.
 * 두 PUT 은 서버처럼 **본문 없이** 저장만 한다(백엔드 ResponseEntity<Void>, 2026-09-22 확인) — 목이 요청을 돌려주던 동안 실서버 버그가 숨어 있었다.
 */
const INITIAL_NOTIFICATIONS: NotificationSettingsDto = {
  notiCoaching: true,
  notiBudgetAlert: true,
  notiTransfer: true,
  notiCleanup: false,
  quietHoursStart: "23:00:00",
  quietHoursEnd: "08:00:00",
};

const INITIAL_COACH: CoachPersonaDto = { coachPersona: "ONSOON" };

let notifications: NotificationSettingsDto = { ...INITIAL_NOTIFICATIONS };
let coach: CoachPersonaDto = { ...INITIAL_COACH };

export function notificationSettingsMock(): NotificationSettingsDto {
  return { ...notifications };
}

export function updateNotificationSettingsMock(request: NotificationSettingsDto): void {
  notifications = { ...request };
}

export function coachPersonaMock(): CoachPersonaDto {
  return { ...coach };
}

export function updateCoachPersonaMock(request: CoachPersonaDto): void {
  coach = { ...request };
}

/** 테스트·개발 재시작용 */
export function resetSettingsMocks(): void {
  settings = { ...INITIAL };
  notifications = { ...INITIAL_NOTIFICATIONS };
  coach = { ...INITIAL_COACH };
}
