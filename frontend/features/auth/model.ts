import { ContractMismatchError } from "@/lib/contract";

/**
 * AUTH 계약 (docs/api-contract.md AUTH, 2026-09-10 백엔드 구현본 확인).
 * 응답 봉투는 api/client.ts 인터셉터가 벗기므로 여기서는 data 안의 모양만 다룬다.
 */
export type AuthUser = { id: number; name: string };

export type LoginRequest = { email: string; password: string };

export type SignupRequest = { email: string; password: string; name: string };

export type SignupResponseDto = { userId: number };

export type LoginResponseDto = {
  accessToken: string;
  refreshToken: string;
  user: { id: number; name: string };
};

export type AuthSession = {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
};

function requiredToken(value: unknown, field: string): string {
  if (typeof value !== "string" || value === "") throw new ContractMismatchError(field);
  return value;
}

export function toAuthSession(dto: LoginResponseDto): AuthSession {
  if (!Number.isInteger(dto.user?.id)) throw new ContractMismatchError("user.id");
  if (typeof dto.user?.name !== "string") throw new ContractMismatchError("user.name");

  return {
    accessToken: requiredToken(dto.accessToken, "accessToken"),
    refreshToken: requiredToken(dto.refreshToken, "refreshToken"),
    user: { id: dto.user.id, name: dto.user.name },
  };
}

/** 이메일 형식만 본다. 비밀번호 규칙은 서버(COMMON_001)가 정한다 — 클라이언트에서 추측하지 않는다. */
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmail(email: string): boolean {
  return EMAIL.test(email.trim());
}

export function canSubmitLogin(email: string, password: string): boolean {
  return isValidEmail(email) && password.length > 0;
}

/** 가입도 같은 기준이다. 이름은 공백만 있으면 안 된다 */
export function canSubmitSignup(email: string, password: string, name: string): boolean {
  return canSubmitLogin(email, password) && name.trim().length > 0;
}

/** PAGE-03 약관 항목. 서버 API 가 없어 목록은 클라이언트 상수다 (docs/frontend-spec.md PAGE-03) */
export type TermsItem = { id: string; label: string; required: boolean };

export const TERMS_ITEMS: readonly TermsItem[] = [
  { id: "service", label: "(필수) 서비스 이용약관 동의", required: true },
  { id: "privacy", label: "(필수) 개인정보 수집 및 이용 동의", required: true },
  { id: "marketing", label: "(선택) 마케팅 정보 수신 동의", required: false },
];

/** 필수 항목을 모두 체크해야 다음으로 갈 수 있다 */
export function canAgreeToTerms(checkedIds: readonly string[]): boolean {
  return TERMS_ITEMS.filter((item) => item.required).every((item) => checkedIds.includes(item.id));
}

export const LOGIN_ROUTE = "/(auth)/login";
export const HOME_ROUTE = "/";

/** 앱 안의 절대 경로만 복귀 대상으로 받는다. `//evil.com` 같은 스킴 상대 주소와 인증 화면은 막는다 (규칙 80) */
const INTERNAL_PATH = /^\/(?!\/)[\w\-./%?=&[\]]*$/;

function isInternalPath(path: string): boolean {
  return INTERNAL_PATH.test(path) && !path.startsWith("/(auth)");
}

/**
 * 로그인 화면 주소. 푸시·딥링크로 들어왔다가 로그아웃 상태면 그 경로를 returnTo 로 달아
 * 로그인 뒤 원래 보려던 화면으로 돌아가게 한다 (규칙 50: 로그인 후 기존 화면 복귀).
 */
export function loginHref(pathname: string): string {
  if (pathname === HOME_ROUTE || !isInternalPath(pathname)) return LOGIN_ROUTE;
  return `${LOGIN_ROUTE}?returnTo=${encodeURIComponent(pathname)}`;
}

/** returnTo 파라미터. 앱 밖 주소나 인증 화면이면 홈으로 돌린다 */
export function parseReturnTo(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === undefined) return HOME_ROUTE;
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return HOME_ROUTE;
  }
  return isInternalPath(decoded) ? decoded : HOME_ROUTE;
}

/**
 * DELETE /users/me 요청 (배포 서버 Swagger 2026-09-20 대조). 현재 비밀번호를 확인한 뒤 계정을 소프트 삭제하고
 * 서버의 Refresh Token 을 지운다. 탈퇴한 이메일로는 다시 가입할 수 없다. 성공 응답은 본문이 없다(204).
 */
export type AccountDeletionRequest = { password: string };

/** 비밀번호를 넣어야 보낼 수 있다. 서버도 빈 값이면 400 COMMON_001 이다 */
export function canSubmitAccountDeletion(password: string): boolean {
  return password.length > 0;
}
