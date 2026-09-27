import Constants, { ExecutionEnvironment } from "expo-constants";
import * as Crypto from "expo-crypto";
import { Platform } from "react-native";

import { unregisterPushDevice } from "@/features/notification/api/notification.api";
import { isInstallationId, shouldShowPushBanner, toPushDataType } from "@/features/notification/model";
import { loadInstallationId, saveInstallationId } from "@/lib/session-storage";

/**
 * 푸시(FCM) 기기 쪽 준비: 실행 환경 판정, 설치 UUID, 알림 채널, 토큰 (FR-NTF-01).
 * expo-notifications 는 웹·테스트 환경에서 불러오지 않도록 쓰는 순간에만 import 한다.
 */

/** 서버 FcmSender 가 이 채널 id 로 보낸다. 채널이 없으면 Android 8+ 에서 알림이 뜨지 않는다 (app.json expo-notifications defaultChannel 과 같다) */
export const PUSH_CHANNEL_ID = "default";
const PUSH_CHANNEL_NAME = "기본 알림";

/** FCM 토큰을 받을 수 있는 환경: Android 의 개발 빌드·설치 앱. 웹과 Expo Go 는 받을 수 없다(서버도 ANDROID 만 받는다) */
export function canUsePush(): boolean {
  return Platform.OS === "android" && Constants.executionEnvironment !== ExecutionEnvironment.StoreClient;
}

/** 이 설치의 UUID. 처음이면 암호학적 난수로 만들어 SecureStore 에 둔다 — 로그아웃해도 유지한다 */
export async function getOrCreateInstallationId(): Promise<string> {
  const saved = await loadInstallationId();
  if (isInstallationId(saved)) return saved;
  const created = Crypto.randomUUID();
  await saveInstallationId(created);
  return created;
}

export async function ensurePushChannel(): Promise<void> {
  const Notifications = await import("expo-notifications");
  await Notifications.setNotificationChannelAsync(PUSH_CHANNEL_ID, {
    name: PUSH_CHANNEL_NAME,
    importance: Notifications.AndroidImportance.HIGH,
  });
}

/** 기기 FCM 토큰. Android 는 알림 권한과 무관하게 받을 수 있다(권한은 표시 여부만 정한다) */
export async function getFcmToken(): Promise<string> {
  const Notifications = await import("expo-notifications");
  const token = await Notifications.getDevicePushTokenAsync();
  return String(token.data);
}

/** FCM 이 토큰을 새로 발급하면 부른다. 반환값으로 구독을 끊는다 */
export async function subscribeFcmTokenRefresh(onToken: (token: string) => void): Promise<() => void> {
  const Notifications = await import("expo-notifications");
  const subscription = Notifications.addPushTokenListener((token) => onToken(String(token.data)));
  return () => subscription.remove();
}

/**
 * 앱을 보고 있는 동안 온 푸시를 어떻게 다룰지 정한다 (FR-NTF-01, 2026-09-20 결정). 이 handler 가 없으면 포그라운드 푸시는 아무 데도 보이지 않는다.
 * 백그라운드와 같은 OS 알림으로 띄워서 탭 처리 경로를 하나로 둔다. 종류별 표시 여부는 model 의 규약을 따른다.
 */
export async function setForegroundPushHandler(): Promise<void> {
  const Notifications = await import("expo-notifications");
  Notifications.setNotificationHandler({
    handleNotification: async (notification) => {
      const show = shouldShowPushBanner(toPushDataType(notification.request.content.data));
      // Android 는 shouldPlaySound 가 false 면 배너도 띄우지 않는다(expo-notifications). shouldSetBadge 는 iOS 전용이라 끈다
      return { shouldShowBanner: show, shouldShowList: show, shouldPlaySound: show, shouldSetBadge: false };
    },
  });
}

/** 앱을 보고 있는 동안 푸시를 받을 때마다 data 를 넘긴다. 제목·본문은 OS 알림에서만 표시한다. 반환값으로 구독을 끊는다 */
export async function subscribePushReceived(onReceived: (data: unknown) => void): Promise<() => void> {
  const Notifications = await import("expo-notifications");
  const subscription = Notifications.addNotificationReceivedListener((notification) => {
    onReceived(notification.request.content.data);
  });
  return () => subscription.remove();
}

/** 앱이 떠 있는 동안 푸시를 탭할 때마다 data 를 넘긴다. 반환값으로 구독을 끊는다 */
export async function subscribePushResponse(onResponse: (data: unknown) => void): Promise<() => void> {
  const Notifications = await import("expo-notifications");
  const subscription = Notifications.addNotificationResponseReceivedListener((response) => onResponse(response.notification.request.content.data));
  return () => subscription.remove();
}

/**
 * 앱을 켠 푸시의 data. 앱이 꺼져 있거나 백그라운드에 있다가 푸시 탭으로 올라온 경우를 위해 마지막 응답을 읽는다.
 * 같은 실행 동안 계속 같은 값을 돌려주므로 호출부가 실행당 한 번만 쓴다. 탭으로 들어온 게 아니면 null.
 */
export async function getLaunchPushData(): Promise<unknown> {
  const Notifications = await import("expo-notifications");
  const response = await Notifications.getLastNotificationResponseAsync();
  return response?.notification.request.content.data ?? null;
}

/**
 * 알림 권한(Android 13+ POST_NOTIFICATIONS)을 설치마다 한 번만 묻는다. 이미 허용됐거나 다시 물을 수 없으면 묻지 않는다.
 * 물어봤는지는 호출부가 기록한다(거절한 사람에게 실행마다 다시 띄우지 않는다).
 */
export async function requestPushPermissionOnce(alreadyAsked: boolean): Promise<"asked" | "skipped"> {
  if (alreadyAsked) return "skipped";
  const Notifications = await import("expo-notifications");
  const current = await Notifications.getPermissionsAsync();
  if (current.granted || !current.canAskAgain) return "skipped";
  await Notifications.requestPermissionsAsync();
  return "asked";
}

/**
 * 로그아웃 직전에 부른다: 이 설치로 푸시가 가지 않게 서버에서 끊는다(Access Token 이 필요해 토큰을 지우기 전이어야 한다).
 * 실패해도 로그아웃은 막지 않는다 — 다음 로그인 때 같은 설치 UUID 로 사용자를 덮어쓴다.
 */
export async function unregisterThisDevice(): Promise<void> {
  if (!canUsePush()) return;
  try {
    const installationId = await loadInstallationId();
    if (isInstallationId(installationId)) await unregisterPushDevice(installationId);
  } catch (error) {
    reportPushSkip("기기 해제", error);
  }
}

/** 푸시 준비 실패는 사용자가 고칠 수 없어 화면에 띄우지 않는다. 개발 중에만 원인(이름·코드, 토큰 제외)을 남긴다 (규칙 50) */
export function reportPushSkip(step: string, error: unknown): void {
  if (!__DEV__) return;
  const reason = error instanceof Error ? error.name : "unknown";
  const code = typeof error === "object" && error !== null && "code" in error ? String(error.code) : "";
  console.warn(`[push] ${step} 건너뜀`, reason, code);
}
