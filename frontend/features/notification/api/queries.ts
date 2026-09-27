import { infiniteQueryOptions, useInfiniteQuery, useMutation, useQueryClient, type InfiniteData, type QueryKey } from "@tanstack/react-query";
import { useEffect } from "react";

import { budgetKeys } from "@/features/budget/api/queries";
import { linkKeys } from "@/features/link/api/queries";
import {
  getNotifications,
  markNotificationRead,
  NOTIFICATION_PAGE_SIZE,
  registerPushDevice,
} from "@/features/notification/api/notification.api";
import { announceCoachFeedback } from "@/features/notification/coachFeedback";
import { isRetryablePushError } from "@/features/notification/errors";
import {
  markNotificationReadInPage,
  pushNotificationId,
  toPushDataType,
  toPushDeviceRequest,
  type InboxNotification,
  type NotificationPage,
  type PushDataType,
  type PushDeviceRequest,
} from "@/features/notification/model";
import {
  canUsePush,
  ensurePushChannel,
  getFcmToken,
  getOrCreateInstallationId,
  reportPushSkip,
  requestPushPermissionOnce,
  setForegroundPushHandler,
  subscribeFcmTokenRefresh,
  subscribePushReceived,
} from "@/features/notification/push";
import { paymentKeys } from "@/features/payment/api/queries";
import { roomKeys } from "@/features/room/api/queries";
import { shopKeys } from "@/features/shop/api/queries";
import { transactionKeys } from "@/features/transaction/api/queries";
import { loadPushPermissionAsked, savePushPermissionAsked } from "@/lib/session-storage";

export const notificationKeys = {
  all: ["notification"] as const,
  list: () => [...notificationKeys.all, "list"] as const,
};

export function notificationListQueryOptions() {
  return infiniteQueryOptions({
    queryKey: notificationKeys.list(),
    queryFn: ({ pageParam, signal }) => getNotifications({ cursor: pageParam, size: NOTIFICATION_PAGE_SIZE }, signal),
    initialPageParam: null as number | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    staleTime: 30_000,
  });
}

/** 알림함(PAGE-28). 스크롤 끝에서 nextCursor 로 다음 쪽을 받는다 */
export function useNotifications() {
  return useInfiniteQuery(notificationListQueryOptions());
}

/** 받아 둔 쪽들을 한 목록으로 */
export function flattenNotifications(data: InfiniteData<NotificationPage> | undefined): InboxNotification[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}

type NotificationListCache = InfiniteData<NotificationPage, number | null>;

/**
 * 알림을 누르면 바로 읽은 모양으로 바꾸고(낙관적 업데이트) 서버에 읽음을 보낸다 — 화면은 응답을 기다리지 않고 대상 화면으로 간다.
 * 실패하면 이전 캐시로 되돌리고, 성공·실패 모두 목록을 다시 받아 서버 상태로 맞춘다 (규칙 10).
 */
export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  const queryKey = notificationKeys.list();

  return useMutation({
    mutationFn: markNotificationRead,
    onMutate: async (notificationId: number) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<NotificationListCache>(queryKey);
      if (previous !== undefined) {
        queryClient.setQueryData<NotificationListCache>(queryKey, {
          ...previous,
          pages: previous.pages.map((page) => markNotificationReadInPage(page, notificationId)),
        });
      }
      return { previous };
    },
    onError: (_error, _notificationId, context) => {
      if (context?.previous !== undefined) queryClient.setQueryData(queryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });
}

type PushDeviceRegistration = { installationId: string; request: PushDeviceRequest };

/** 서버가 이미 3회 재시도한 뒤의 409 라 앱은 두 번까지만 더 보낸다 */
const MAX_PUSH_REGISTER_RETRY = 2;

/**
 * 로그인한 동안 이 설치를 푸시 대상으로 등록하고, FCM 이 토큰을 새로 주면 다시 등록한다 (FR-NTF-01). (app) 레이아웃이 한 번 쓴다.
 * FCM 이라는 외부 시스템과 맞추는 일이라 effect 로 둔다 (규칙 10). 등록은 멱등(PUT)이라 앱을 켤 때마다 보내도 된다.
 * 실패해도 화면을 막지 않고 다음 실행에서 다시 등록한다. 웹·Expo Go 는 토큰이 없어 아무것도 하지 않는다.
 */
export function usePushDeviceRegistration(enabled: boolean) {
  const { mutate } = useMutation({
    mutationFn: ({ installationId, request }: PushDeviceRegistration) => registerPushDevice(installationId, request),
    retry: (failureCount, error) => isRetryablePushError(error) && failureCount < MAX_PUSH_REGISTER_RETRY,
    onError: (error) => reportPushSkip("기기 등록", error),
  });

  useEffect(() => {
    if (!enabled || !canUsePush()) return;
    let active = true;
    let unsubscribe: (() => void) | null = null;

    const register = async (token: string) => {
      const request = toPushDeviceRequest(token);
      if (request === null || !active) return;
      mutate({ installationId: await getOrCreateInstallationId(), request });
    };

    const start = async () => {
      await ensurePushChannel();
      const stop = await subscribeFcmTokenRefresh((token) => {
        register(token).catch((error: unknown) => reportPushSkip("토큰 갱신 등록", error));
      });
      if (!active) {
        stop();
        return;
      }
      unsubscribe = stop;
      await register(await getFcmToken());
    };
    start().catch((error: unknown) => reportPushSkip("푸시 준비", error));

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [enabled, mutate]);
}

/**
 * 푸시 종류별로 함께 새로 받을 화면 데이터 (data 규약은 docs/api-contract.md NOTIFICATION).
 * 알림함은 종류와 무관하게 갱신하므로 여기 넣지 않는다. 연출은 서버에서 다시 받을 데이터가 없다.
 * 지금 서버의 COACHING 푸시는 "새로 정리할 거래가 있어요"(refId = 거래 id)다. 새 거래는 미확정 목록뿐 아니라
 * 거래 내역·자산 탭 최근 거래에도 들어가므로 거래 조회 전체를 새로 받는다 — 미확정만 받으면 목록이 늦게 따라온다 (2026-09-22).
 * 홈의 코인 수는 코인 잔액 조회가 아니라 방 홈(GET /room)의 값이라 COIN_GRANTED 는 방 홈도 함께 받는다. WARNING 은 지금 서버가 보내는 미납 경고다(Notion 규약의 PAYMENT_RISK).
 */
function affectedQueryKeys(type: PushDataType): QueryKey[] {
  switch (type) {
    case "CLASSIFY_QUESTION":
    case "CLEANUP":
    case "COACHING":
      return [transactionKeys.all];
    case "BUDGET_ALERT":
      return [budgetKeys.current(), roomKeys.home()];
    case "TRANSFER_REQUEST":
      return [paymentKeys.transfers()];
    case "PAYMENT_RISK":
    case "WARNING":
      return [paymentKeys.calendar()];
    case "SUBSCRIPTION_CARD":
      return [paymentKeys.fixedExpenses()];
    case "COIN_GRANTED":
      return [shopKeys.coins(), roomKeys.home()];
    case "NEW_LINK_FOUND":
      return [linkKeys.candidates()];
    case "REACTION":
    case "UNKNOWN":
      return [];
  }
}

/**
 * 앱을 보고 있는 동안 온 푸시를 OS 배너로 띄우고 관련 화면 데이터를 새로 받는다 (FR-NTF-01, 2026-09-20 결정).
 * handler 가 없으면 포그라운드 푸시는 아무 데도 보이지 않아 (app) 레이아웃이 로그인 동안 한 번 켠다.
 * FCM 이라는 외부 시스템에 붙는 일이라 effect 로 둔다 (규칙 10). 웹·Expo Go 는 푸시가 오지 않아 아무것도 하지 않는다.
 */
export function usePushForegroundDisplay(enabled: boolean) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || !canUsePush()) return;
    let active = true;
    let unsubscribe: (() => void) | null = null;

    const start = async () => {
      await setForegroundPushHandler();
      const stop = await subscribePushReceived((data) => {
        const type = toPushDataType(data);
        const keys: QueryKey[] = [notificationKeys.all, ...affectedQueryKeys(type)];
        for (const queryKey of keys) queryClient.invalidateQueries({ queryKey });
        // 푸시 문구는 OS 알림에서 보여 주고, 홈 말풍선에는 API가 준비한 AI 코칭만 담는다.
        const notificationId = pushNotificationId(data);
        if (type === "BUDGET_ALERT" && notificationId !== null) void announceCoachFeedback(notificationId);
      });
      if (!active) {
        stop();
        return;
      }
      unsubscribe = stop;
    };
    start().catch((error: unknown) => reportPushSkip("포그라운드 표시", error));

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [enabled, queryClient]);
}

/**
 * 알림 권한(Android 13+)을 설치마다 한 번 묻는다. 탭 화면에 들어온 뒤에만 켜서 온보딩 흐름을 시스템 창으로 끊지 않는다.
 * 토큰 등록은 권한과 무관하게 먼저 해 두고, 권한은 알림을 화면에 띄울지만 정한다.
 */
export function usePushPermissionPrompt(enabled: boolean) {
  useEffect(() => {
    if (!enabled || !canUsePush()) return;
    const ask = async () => {
      const result = await requestPushPermissionOnce(await loadPushPermissionAsked());
      if (result === "asked") await savePushPermissionAsked();
    };
    ask().catch((error: unknown) => reportPushSkip("알림 권한", error));
  }, [enabled]);
}

