import {
  notificationSettingsMock,
  resetSettingsMocks,
  transferSettingsMock,
  updateNotificationSettingsMock,
  updateTransferSettingsMock,
} from "@/api/mocks/settings";
import {
  isSettingsDirty,
  quietHoursError,
  quietHoursLabel,
  toCoachPersona,
  toCoachPersonaRequest,
  toNotificationSettings,
  toNotificationSettingsRequest,
  withNotificationKind,
  withQuietHours,
  settingsFormError,
  toSettingsForm,
  toTransferSettings,
  toTransferSettingsRequest,
  type NotificationSettingsDto,
  type TransferSettingsForm,
} from "@/features/settings/model";
import { ContractMismatchError } from "@/lib/contract";

const settings = toTransferSettings(transferSettingsMock());
const unset = toTransferSettings({ transferConsent: true, transferLimitOnce: null, transferLimitDaily: null });

describe("toTransferSettings", () => {
  it("한도를 KRW 로 바꾸고 계약과 다른 값은 불일치로 본다", () => {
    expect(settings).toEqual({ consent: true, limitOnce: "500000", limitDaily: "1000000" });
    expect(() => toTransferSettings({ ...transferSettingsMock(), transferLimitOnce: 1.5 })).toThrow(ContractMismatchError);
  });

  it("한도 null 은 미설정이라 그대로 두고 입력칸은 비운다", () => {
    expect(unset).toEqual({ consent: true, limitOnce: null, limitDaily: null });
    expect(toSettingsForm(unset)).toEqual({ consent: true, limitOnce: "", limitDaily: "" });
  });
});

describe("settingsFormError", () => {
  const form: TransferSettingsForm = toSettingsForm(settings);

  it("동의를 켰을 때만 한도를 검사하고 1회 한도가 1일 한도를 넘으면 막는다", () => {
    expect(settingsFormError(form)).toBeNull();
    expect(settingsFormError({ ...form, limitOnce: "" })).toContain("1회 한도");
    expect(settingsFormError({ ...form, limitDaily: "0" })).toContain("1일 한도");
    expect(settingsFormError({ ...form, limitOnce: "2000000" })).toContain("1일 한도보다");
    expect(settingsFormError({ consent: false, limitOnce: "", limitDaily: "" })).toBeNull();
    expect(settingsFormError(toSettingsForm(unset))).toContain("1회 한도");
  });
});

describe("isSettingsDirty · toTransferSettingsRequest", () => {
  const form = toSettingsForm(settings);

  it("바뀐 값이 있을 때만 dirty 다", () => {
    expect(isSettingsDirty(form, settings)).toBe(false);
    expect(isSettingsDirty({ ...form, consent: false }, settings)).toBe(true);
    expect(isSettingsDirty({ ...form, limitOnce: "400000" }, settings)).toBe(true);
  });

  it("동의를 꺼도 한도는 서버가 들고 있어야 해서 원래 값을 그대로 보낸다", () => {
    expect(toTransferSettingsRequest({ ...form, limitOnce: "400000" }, settings)).toEqual({
      transferConsent: true,
      transferLimitOnce: 400000,
      transferLimitDaily: 1000000,
    });
    expect(toTransferSettingsRequest({ consent: false, limitOnce: "", limitDaily: "" }, settings)).toEqual({
      transferConsent: false,
      transferLimitOnce: 500000,
      transferLimitDaily: 1000000,
    });
    expect(() => toTransferSettingsRequest({ ...form, limitOnce: "0" }, settings)).toThrow();
  });

  it("한도가 미설정이면 빈 입력은 바뀐 게 아니고, 동의를 끄고 저장하면 null 을 그대로 보낸다", () => {
    const unsetForm = toSettingsForm(unset);
    expect(isSettingsDirty(unsetForm, unset)).toBe(false);
    expect(toTransferSettingsRequest({ ...unsetForm, consent: false }, unset)).toEqual({
      transferConsent: false,
      transferLimitOnce: null,
      transferLimitDaily: null,
    });
  });
});

describe("설정 목 — 저장한 값이 다시 조회된다", () => {
  afterEach(() => resetSettingsMocks());

  it("PUT 한 값이 GET 에 그대로 나온다", () => {
    updateTransferSettingsMock({ transferConsent: false, transferLimitOnce: 300000, transferLimitDaily: 700000 });
    expect(transferSettingsMock()).toEqual({ transferConsent: false, transferLimitOnce: 300000, transferLimitDaily: 700000 });
  });
});

/** 계약 예시(Swagger NotificationSettingsResponse) */
function notificationDto(overrides: Partial<NotificationSettingsDto> = {}): NotificationSettingsDto {
  return {
    notiCoaching: true,
    notiBudgetAlert: true,
    notiTransfer: true,
    notiCleanup: false,
    quietHoursStart: "23:00:00",
    quietHoursEnd: "08:00:00",
    ...overrides,
  };
}

describe("알림 설정 (GET·PUT /settings/notifications)", () => {
  it("계약 예시를 화면 모델로 바꾸고 시각은 분까지만 쓴다", () => {
    expect(toNotificationSettings(notificationDto())).toEqual({
      enabled: { coaching: true, budgetAlert: true, transfer: true, cleanup: false },
      quietHours: { start: "23:00", end: "08:00" },
    });
    expect(toNotificationSettings(notificationDto({ quietHoursStart: "23:00", quietHoursEnd: "08:00" })).quietHours).toEqual({
      start: "23:00",
      end: "08:00",
    });
  });

  it("방해 금지는 두 쪽이 다 있을 때만 범위이고, 한쪽만 오면 끈 것으로 본다", () => {
    expect(toNotificationSettings(notificationDto({ quietHoursStart: null, quietHoursEnd: null })).quietHours).toBeNull();
    expect(toNotificationSettings(notificationDto({ quietHoursEnd: null })).quietHours).toBeNull();
  });

  it("시각이 계약 형식이 아니면 계약 불일치로 막는다", () => {
    expect(() => toNotificationSettings(notificationDto({ quietHoursStart: "24:00:00" }))).toThrow(ContractMismatchError);
    expect(() => toNotificationSettings(notificationDto({ quietHoursEnd: "8시" }))).toThrow(ContractMismatchError);
  });

  it("요청은 초까지 붙이고, 방해 금지를 끄면 두 쪽 모두 null 이다", () => {
    const current = toNotificationSettings(notificationDto());
    expect(toNotificationSettingsRequest(current)).toEqual(notificationDto());
    expect(toNotificationSettingsRequest(withQuietHours(current, null))).toEqual(
      notificationDto({ quietHoursStart: null, quietHoursEnd: null })
    );
  });

  it("토글 하나만 바꿔도 나머지는 그대로다", () => {
    const current = toNotificationSettings(notificationDto());
    const next = withNotificationKind(current, "cleanup", true);
    expect(next.enabled).toEqual({ coaching: true, budgetAlert: true, transfer: true, cleanup: true });
    expect(next.quietHours).toEqual(current.quietHours);
  });

  it("시작과 종료가 같으면 막고, 자정을 지나는 범위는 허용한다", () => {
    expect(quietHoursError({ start: "23:00", end: "23:00" })).not.toBeNull();
    expect(quietHoursError({ start: "23:00", end: "08:00" })).toBeNull();
    expect(quietHoursError(null)).toBeNull();
    expect(quietHoursLabel({ start: "23:00", end: "08:00" })).toBe("23:00 ~ 08:00");
    expect(quietHoursLabel(null)).toBe("사용 안 함");
  });

  it("목 PUT 은 서버처럼 본문 없이 저장만 하고, 다음 GET 이 저장한 값을 준다", () => {
    resetSettingsMocks();
    const request = notificationDto({ notiCleanup: true, quietHoursStart: null, quietHoursEnd: null });
    expect(updateNotificationSettingsMock(request)).toBeUndefined();
    expect(notificationSettingsMock()).toEqual(request);
    resetSettingsMocks();
  });
});

describe("코치 말투 (GET·PUT /settings/coach)", () => {
  it("계약의 4종만 받고 모르는 값은 UNKNOWN 으로 흡수한다", () => {
    expect(toCoachPersona({ coachPersona: "DODO" })).toBe("DODO");
    expect(toCoachPersona({ coachPersona: "PLAIN" })).toBe("PLAIN");
    expect(toCoachPersona({ coachPersona: "CAT" })).toBe("UNKNOWN");
  });

  it("모르는 값은 서버로 되돌려 보내지 않는다", () => {
    expect(toCoachPersonaRequest("JIBANG")).toEqual({ coachPersona: "JIBANG" });
    expect(() => toCoachPersonaRequest("UNKNOWN")).toThrow();
  });
});
