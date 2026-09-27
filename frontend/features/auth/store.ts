import { create } from "zustand";

import type { AuthUser } from "@/features/auth/model";

/** 사용자 정보만 둔다. 토큰은 규칙 80 에 따라 lib/session-storage.ts(expo-secure-store)가 맡는다. */
export type { AuthUser };

/** loading 은 저장된 세션을 아직 읽는 중이라는 뜻이다. 이때 로그인 화면을 띄우면 자동 로그인이 깜빡인다. */
export type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthState = {
  user: AuthUser | null;
  status: AuthStatus;
  /** 약관 동의 여부. null 은 아직 읽지 않았다는 뜻이다 (PAGE-03) */
  termsAgreed: boolean | null;
  /** 온보딩(금융망 연결 → 예산 확정) 완료 여부. 기기 기록이며 서버 판정이 생기면 바꾼다 */
  onboardingDone: boolean | null;
  signIn: (user: AuthUser, termsAgreed: boolean, onboardingDone: boolean) => void;
  signOut: () => void;
  agreeToTerms: () => void;
  completeOnboarding: () => void;
  /** 앱 시작 시 저장된 세션을 반영한다. 토큰만 있고 사용자 정보가 없으면 user 는 null 로 둔다. */
  restore: (user: AuthUser | null, authenticated: boolean, termsAgreed: boolean, onboardingDone: boolean) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "loading",
  termsAgreed: null,
  onboardingDone: null,
  signIn: (user, termsAgreed, onboardingDone) => set({ user, status: "authenticated", termsAgreed, onboardingDone }),
  signOut: () => set({ user: null, status: "anonymous", termsAgreed: null, onboardingDone: null }),
  agreeToTerms: () => set({ termsAgreed: true }),
  completeOnboarding: () => set({ onboardingDone: true }),
  restore: (user, authenticated, termsAgreed, onboardingDone) =>
    set({ user, status: authenticated ? "authenticated" : "anonymous", termsAgreed, onboardingDone }),
}));

export const selectUserName = (state: AuthState): string | null => state.user?.name ?? null;
export const selectAuthStatus = (state: AuthState): AuthStatus => state.status;
export const selectTermsAgreed = (state: AuthState): boolean | null => state.termsAgreed;
export const selectOnboardingDone = (state: AuthState): boolean | null => state.onboardingDone;
