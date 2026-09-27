import { useRouter } from "expo-router";
import { useEffect, useRef } from "react";

import { announceCoachFeedback } from "@/features/notification/coachFeedback";
import { pushNotificationHref, pushNotificationId, toPushDataType } from "@/features/notification/model";
import { canUsePush, getLaunchPushData, reportPushSkip, subscribePushResponse } from "@/features/notification/push";

/**
 * 푸시를 탭하면 대상 화면으로 보낸다 (FR-NTF-01, 진입 화면은 docs/frontend-spec.md §3 푸시 딥링크 매핑).
 * 앱이 떠 있는 동안의 탭은 구독으로 받고, 앱이 꺼져 있다 푸시로 켜진 경우는 마지막 응답을 실행당 한 번만 읽는다
 * (같은 값이 계속 나와 effect 가 다시 돌 때 또 이동하지 않게 한다).
 * FCM 이라는 외부 시스템에 붙는 일이라 effect 로 둔다 (규칙 10). 로그인한 동안만 켜므로 로그아웃 상태로 들어오면
 * (app) 레이아웃이 로그인으로 보냈다가 로그인 뒤 대상 화면으로 간다. 웹·Expo Go 는 푸시가 오지 않아 아무것도 하지 않는다.
 */
export function usePushDeepLink(enabled: boolean) {
  const router = useRouter();
  const launchHandled = useRef(false);

  useEffect(() => {
    if (!enabled || !canUsePush()) return;
    let active = true;
    let unsubscribe: (() => void) | null = null;

    const go = (data: unknown) => {
      const href = pushNotificationHref(data);
      if (href !== null && active) router.push(href);
      // 예산 알림을 눌러 들어오면 코치 피드백을 받아 두었다가 홈에서 말한다 (-184)
      const notificationId = pushNotificationId(data);
      if (toPushDataType(data) === "BUDGET_ALERT" && notificationId !== null) void announceCoachFeedback(notificationId);
    };

    const start = async () => {
      const stop = await subscribePushResponse(go);
      if (!active) {
        stop();
        return;
      }
      unsubscribe = stop;
      if (launchHandled.current) return;
      launchHandled.current = true;
      go(await getLaunchPushData());
    };
    start().catch((error: unknown) => reportPushSkip("푸시 딥링크", error));

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [enabled, router]);
}
