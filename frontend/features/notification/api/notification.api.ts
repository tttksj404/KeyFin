import { api, isMocked } from "@/api/client";
import { withMockLatency } from "@/api/mocks/latency";
import {
  coachFeedbackMock,
  markNotificationReadMock,
  notificationListMock,
  registerPushDeviceMock,
  unregisterPushDeviceMock,
} from "@/api/mocks/notification";
import {
  toCoachFeedback,
  toNotificationPage,
  type CoachFeedback,
  type CoachFeedbackDto,
  type NotificationListDto,
  type NotificationPage,
  type PushDeviceRequest,
} from "@/features/notification/model";

export type NotificationPageParams = { cursor: number | null; size: number };

/** 계약 기본값(size 20)과 같다 */
export const NOTIFICATION_PAGE_SIZE = 20;

/**
 * GET /notifications?cursor=&size= — 본인 알림, 최신순 커서 페이지 (FR-NTF-02).
 * unreadOnly 는 보내지 않는다(알림함은 읽은 것도 함께 보여 준다). 조회만으로 읽음 처리되지 않는다.
 */
export async function getNotifications(page: NotificationPageParams, signal?: AbortSignal): Promise<NotificationPage> {
  if (isMocked("notification")) return toNotificationPage(await withMockLatency(notificationListMock(page), signal));
  const { data } = await api.get<NotificationListDto>("/notifications", {
    params: { cursor: page.cursor ?? undefined, size: page.size },
    signal,
  });
  return toNotificationPage(data);
}

/**
 * PATCH /notifications/{id}/read — 본문 없음, data 는 null. 이미 읽은 알림도 성공(멱등).
 * 남의 알림·없는 알림은 404 NOTI_001. 이체 승인·조치 필요 여부는 바꾸지 않는다.
 */
export async function markNotificationRead(notificationId: number): Promise<void> {
  if (isMocked("notification")) {
    markNotificationReadMock(notificationId);
    await withMockLatency(undefined);
    return;
  }
  await api.patch(`/notifications/${notificationId}/read`);
}

/**
 * GET /notifications/{id}/coach-feedback — 예산 구간 알림의 코치 피드백 (-182). 상태는 모두 200, 남의 알림·만료는 NONE.
 */
export async function getCoachFeedback(notificationId: number, signal?: AbortSignal): Promise<CoachFeedback> {
  if (isMocked("notification")) return toCoachFeedback(await withMockLatency(coachFeedbackMock(notificationId), signal));
  const { data } = await api.get<CoachFeedbackDto>(`/notifications/${notificationId}/coach-feedback`, { signal });
  return toCoachFeedback(data);
}

/**
 * PUT /me/push-devices/{installationId} — 이 설치의 FCM 토큰 등록·갱신 겸용(멱등, FR-NTF-01). data 는 null.
 * 같은 설치면 사용자·토큰을 덮어쓰고, 같은 토큰이 다른 설치에 묶여 있으면 서버가 그 연결을 푼다(계정 전환·재설치).
 * 오류: 400 COMMON_001/002(UUID·토큰·플랫폼) · 404 USER_001 · 409 PUSH_001(동시 변경, 다시 보내도 된다).
 */
export async function registerPushDevice(installationId: string, request: PushDeviceRequest): Promise<void> {
  if (isMocked("notification")) {
    registerPushDeviceMock(installationId, request);
    await withMockLatency(undefined);
    return;
  }
  await api.put(`/me/push-devices/${installationId}`, request);
}

/** DELETE /me/push-devices/{installationId} — 로그아웃 때 이 설치로 푸시가 가지 않게 한다. 이미 해제됐거나 남의 설치여도 200 */
export async function unregisterPushDevice(installationId: string): Promise<void> {
  if (isMocked("notification")) {
    unregisterPushDeviceMock(installationId);
    await withMockLatency(undefined);
    return;
  }
  await api.delete(`/me/push-devices/${installationId}`);
}

