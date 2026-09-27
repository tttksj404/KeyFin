import * as React from "react";

import { setUnauthorizedHandler } from "@/api/client";
import { useAuthStore } from "@/features/auth/store";
import { seedOnboardedMocks } from "@/api/mocks/onboarding";
import { loadOnboardingDone, loadSessionUser, loadTermsAgreed, loadTokens } from "@/lib/session-storage";

/**
 * 앱 시작 시 저장된 세션을 스토어에 되살린다 (네이티브만 — 웹은 저장소가 메모리라 항상 비로그인으로 시작한다).
 * 토큰 갱신까지 실패했을 때 api 층이 부를 수 있도록 로그아웃 처리도 여기서 등록한다.
 */
export function useSessionBootstrap(): void {
  const restore = useAuthStore((state) => state.restore);
  const signOut = useAuthStore((state) => state.signOut);

  React.useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const { accessToken } = await loadTokens();
      const user = accessToken === null ? null : await loadSessionUser();
      const termsAgreed = user === null ? false : await loadTermsAgreed(user.id);
      const onboardingDone = user === null ? false : await loadOnboardingDone(user.id);
      if (onboardingDone) seedOnboardedMocks();
      if (!cancelled) restore(user, accessToken !== null, termsAgreed, onboardingDone);
    }

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [restore]);

  React.useEffect(() => {
    setUnauthorizedHandler(signOut);
    return () => setUnauthorizedHandler(null);
  }, [signOut]);
}
