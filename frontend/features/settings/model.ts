import { ContractMismatchError } from "@/lib/contract";
import { compareKRW, fromServerWon, toWon, type KRW } from "@/lib/money";

/**
 * GET/PUT /settings/transfer 계약 (docs/api-contract.md USER, FR-PAY-04).
 * 이체 동의와 한도는 이체 실행 직전 서버가 다시 검사하는 값이라 화면은 보내고 받은 값만 보여준다.
 * 한도가 null 이면 미설정이다(가입 직후 기본값).
 */
export type TransferSettingsDto = {
  transferConsent: boolean;
  transferLimitOnce: number | null;
  transferLimitDaily: number | null;
};

export type TransferSettings = {
  consent: boolean;
  limitOnce: KRW | null;
  limitDaily: KRW | null;
};

function limit(value: number | null, field: string): KRW | null {
  if (value === null) return null;
  try {
    return fromServerWon(value);
  } catch {
    throw new ContractMismatchError(field);
  }
}

export function toTransferSettings(dto: TransferSettingsDto): TransferSettings {
  if (typeof dto.transferConsent !== "boolean") throw new ContractMismatchError("transferConsent");
  return {
    consent: dto.transferConsent,
    limitOnce: limit(dto.transferLimitOnce, "transferLimitOnce"),
    limitDaily: limit(dto.transferLimitDaily, "transferLimitDaily"),
  };
}

/** 설정 화면의 입력값. 금액은 입력 중 상태를 그대로 두려고 문자열이고, 미설정 한도는 빈 칸이다 */
export type TransferSettingsForm = {
  consent: boolean;
  limitOnce: string;
  limitDaily: string;
};

export function toSettingsForm(settings: TransferSettings): TransferSettingsForm {
  return { consent: settings.consent, limitOnce: settings.limitOnce ?? "", limitDaily: settings.limitDaily ?? "" };
}

/**
 * 저장할 수 없는 이유. 없으면 null.
 * 동의를 끄면 한도는 쓰이지 않으니 검사하지 않는다. 1회 한도가 1일 한도보다 클 수 없다는 규칙은
 * 서버도 같은 방향으로 검사한다(USER_005).
 */
export function settingsFormError(form: TransferSettingsForm): string | null {
  if (!form.consent) return null;
  if (form.limitOnce === "" || toWon(form.limitOnce) <= 0n) return "1회 한도를 입력해 주세요.";
  if (form.limitDaily === "" || toWon(form.limitDaily) <= 0n) return "1일 한도를 입력해 주세요.";
  if (compareKRW(form.limitOnce, form.limitDaily) > 0) return "1회 한도는 1일 한도보다 클 수 없어요.";
  return null;
}

/** 바뀐 게 없으면 저장 버튼을 켜지 않는다 */
export function isSettingsDirty(form: TransferSettingsForm, settings: TransferSettings): boolean {
  return (
    form.consent !== settings.consent ||
    form.limitOnce !== (settings.limitOnce ?? "") ||
    form.limitDaily !== (settings.limitDaily ?? "")
  );
}

function toServerLimit(value: KRW | null): number | null {
  return value === null ? null : Number(toWon(value));
}

/** 화면 값 → PUT /settings/transfer 요청. 동의를 꺼도 한도는 서버가 들고 있어야 해서 원래 값(미설정이면 null)을 그대로 보낸다 */
export function toTransferSettingsRequest(form: TransferSettingsForm, current: TransferSettings): TransferSettingsDto {
  const error = settingsFormError(form);
  if (error !== null) throw new Error(error);
  const limitOnce = form.consent ? form.limitOnce : current.limitOnce;
  const limitDaily = form.consent ? form.limitDaily : current.limitDaily;
  return {
    transferConsent: form.consent,
    transferLimitOnce: toServerLimit(limitOnce),
    transferLimitDaily: toServerLimit(limitDaily),
  };
}

/* ───────────── 알림 설정: GET·PUT /settings/notifications (배포 서버 Swagger 2026-09-20 대조, FR-NTF-03) ───────────── */

/**
 * 유형별 수신 여부 4종과 방해 금지 시간이다. 방해 금지를 쓰지 않으면 시작·종료가 모두 null 이고,
 * 자정을 지나는 범위(23:00~08:00)도 서버가 받는다. 시각은 응답이 "HH:mm:ss" 라 화면은 분까지만 쓴다.
 * 한쪽만 null 이거나 범위가 없는 값은 서버가 400 USER_009 로 막는다 — 화면이 먼저 같은 규칙으로 검사한다.
 */
export type NotificationSettingsDto = {
  notiCoaching: boolean;
  notiBudgetAlert: boolean;
  notiTransfer: boolean;
  notiCleanup: boolean;
  quietHoursStart: string | null;
  quietHoursEnd: string | null;
};

/** 알림 종류. 화면의 토글 순서이기도 하다 */
export const NOTIFICATION_KINDS = ["coaching", "budgetAlert", "transfer", "cleanup"] as const;
export type NotificationKind = (typeof NOTIFICATION_KINDS)[number];

/** "HH:mm" 두 쪽. 시작이 종료보다 늦으면 자정을 지나는 범위다 */
export type QuietHours = { start: string; end: string };

export type NotificationSettings = {
  enabled: Record<NotificationKind, boolean>;
  /** 쓰지 않으면 null */
  quietHours: QuietHours | null;
};

const LOCAL_TIME = /^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/;

function toClockTime(value: string, field: string): string {
  if (!LOCAL_TIME.test(value)) throw new ContractMismatchError(field);
  return value.slice(0, 5);
}

export function toNotificationSettings(dto: NotificationSettingsDto): NotificationSettings {
  const start = dto.quietHoursStart;
  const end = dto.quietHoursEnd;
  // 한쪽만 온 응답은 범위로 쓸 수 없어 방해 금지를 끈 것으로 본다 (규칙 90: 화면을 깨뜨리지 않는다)
  const quietHours =
    start !== null && end !== null
      ? { start: toClockTime(start, "quietHoursStart"), end: toClockTime(end, "quietHoursEnd") }
      : null;

  return {
    enabled: {
      coaching: dto.notiCoaching,
      budgetAlert: dto.notiBudgetAlert,
      transfer: dto.notiTransfer,
      cleanup: dto.notiCleanup,
    },
    quietHours,
  };
}

/** 서버 LocalTime 은 "HH:mm" 도 받지만 응답 형식과 같게 초까지 붙여 보낸다 */
function toServerTime(value: string): string {
  return `${value}:00`;
}

export function toNotificationSettingsRequest(settings: NotificationSettings): NotificationSettingsDto {
  return {
    notiCoaching: settings.enabled.coaching,
    notiBudgetAlert: settings.enabled.budgetAlert,
    notiTransfer: settings.enabled.transfer,
    notiCleanup: settings.enabled.cleanup,
    quietHoursStart: settings.quietHours === null ? null : toServerTime(settings.quietHours.start),
    quietHoursEnd: settings.quietHours === null ? null : toServerTime(settings.quietHours.end),
  };
}

export function withNotificationKind(settings: NotificationSettings, kind: NotificationKind, enabled: boolean): NotificationSettings {
  return { ...settings, enabled: { ...settings.enabled, [kind]: enabled } };
}

export function withQuietHours(settings: NotificationSettings, quietHours: QuietHours | null): NotificationSettings {
  return { ...settings, quietHours };
}

/** 저장할 수 없는 이유. 시작과 끝이 같으면 범위가 없어 서버도 400 USER_009 로 막는다 */
export function quietHoursError(quietHours: QuietHours | null): string | null {
  if (quietHours === null) return null;
  return quietHours.start === quietHours.end ? "시작과 종료 시각을 다르게 골라 주세요." : null;
}

/** "23:00 ~ 08:00" · 끄면 "사용 안 함" */
export function quietHoursLabel(quietHours: QuietHours | null): string {
  return quietHours === null ? "사용 안 함" : `${quietHours.start} ~ ${quietHours.end}`;
}

/* ───────────── 코치 말투: GET·PUT /settings/coach (배포 서버 Swagger 2026-09-20 대조) ───────────── */

/** 서버 enum 4종. api-contract 의 3종(DODO·ONSOON·JIBANG)에 PLAIN 이 더 있다 */
export const COACH_PERSONAS = ["PLAIN", "DODO", "ONSOON", "JIBANG"] as const;
export type CoachPersona = (typeof COACH_PERSONAS)[number] | "UNKNOWN";

export type CoachPersonaDto = { coachPersona: string };

export function toCoachPersona(dto: CoachPersonaDto): CoachPersona {
  return (COACH_PERSONAS as readonly string[]).includes(dto.coachPersona) ? (dto.coachPersona as CoachPersona) : "UNKNOWN";
}

/** 모르는 값은 서버에 되돌려 보내지 않는다 — 고를 수 있는 건 계약에 있는 4종뿐이다 */
export function toCoachPersonaRequest(persona: CoachPersona): CoachPersonaDto {
  if (persona === "UNKNOWN") throw new Error("고를 수 없는 코치 말투입니다.");
  return { coachPersona: persona };
}
