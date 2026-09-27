import { api, isMocked } from "@/api/client";
import { withMockLatency } from "@/api/mocks/latency";
import {
  coachPersonaMock,
  notificationSettingsMock,
  transferSettingsMock,
  updateCoachPersonaMock,
  updateNotificationSettingsMock,
  updateTransferSettingsMock,
} from "@/api/mocks/settings";
import {
  toCoachPersona,
  toNotificationSettings,
  toNotificationSettingsRequest,
  toTransferSettings,
  type CoachPersona,
  type CoachPersonaDto,
  type NotificationSettings,
  type NotificationSettingsDto,
  type TransferSettings,
  type TransferSettingsDto,
} from "@/features/settings/model";

/** GET /settings/transfer — 이체 동의와 1회·1일 한도 (docs/api-contract.md USER, FR-PAY-04). 파라미터 없음 */
export async function getTransferSettings(signal?: AbortSignal): Promise<TransferSettings> {
  if (isMocked("settings")) return toTransferSettings(await withMockLatency(transferSettingsMock(), signal));
  const { data } = await api.get<TransferSettingsDto>("/settings/transfer", { signal });
  return toTransferSettings(data);
}

/** PUT /settings/transfer — 요청·응답 모두 TransferSettings. 돈이 움직이는 설정이라 자동 재시도하지 않는다 (규칙 80) */
export async function updateTransferSettings(request: TransferSettingsDto): Promise<TransferSettings> {
  if (isMocked("settings")) return toTransferSettings(await withMockLatency(updateTransferSettingsMock(request)));
  const { data } = await api.put<TransferSettingsDto>("/settings/transfer", request);
  return toTransferSettings(data);
}

/** GET /settings/notifications — 유형별 수신 여부와 방해 금지 시간 (FR-NTF-03). 오류: 404 USER_001·USER_006 */
export async function getNotificationSettings(signal?: AbortSignal): Promise<NotificationSettings> {
  if (isMocked("settings")) return toNotificationSettings(await withMockLatency(notificationSettingsMock(), signal));
  const { data } = await api.get<NotificationSettingsDto>("/settings/notifications", { signal });
  return toNotificationSettings(data);
}

/**
 * PUT /settings/notifications — 유형 4종과 방해 금지를 한 번에 보낸다(부분 수정이 없다).
 * 시작·종료를 모두 null 로 보내면 방해 금지가 풀린다. 오류: 400 COMMON_001·USER_009(방해 금지 범위) · 404 USER_001·USER_006.
 * **응답 본문이 없다**(백엔드 UserSettingsController 가 ResponseEntity<Void>, 2026-09-22 확인) — 옛 기재처럼 새 설정을 돌려주지 않는다.
 * 본문을 읽으려다 실패해 토글이 되돌아가던 버그의 원인이라 성공 여부만 본다. 새 값은 보낸 값이고, 서버 값은 다시 조회한다.
 */
export async function updateNotificationSettings(settings: NotificationSettings): Promise<void> {
  const request = toNotificationSettingsRequest(settings);
  if (isMocked("settings")) return withMockLatency(updateNotificationSettingsMock(request));
  await api.put<void>("/settings/notifications", request);
}

/** GET /settings/coach — 지금 고른 코치 말투 */
export async function getCoachPersona(signal?: AbortSignal): Promise<CoachPersona> {
  if (isMocked("settings")) return toCoachPersona(await withMockLatency(coachPersonaMock(), signal));
  const { data } = await api.get<CoachPersonaDto>("/settings/coach", { signal });
  return toCoachPersona(data);
}

/**
 * PUT /settings/coach — PLAIN·DODO·ONSOON·JIBANG 중 하나. 오류: 400 COMMON_001(누락)·COMMON_002(지원하지 않는 값).
 * 알림 설정과 같이 **응답 본문이 없다**(ResponseEntity<Void>) — 본문을 말투로 읽으면 UNKNOWN 이 되어 체크가 사라지던 원인이다.
 */
export async function updateCoachPersona(request: CoachPersonaDto): Promise<void> {
  if (isMocked("settings")) return withMockLatency(updateCoachPersonaMock(request));
  await api.put<void>("/settings/coach", request);
}
