import { ApiError } from "@/api/error";
import type {
  AccountDeletionRequest,
  AuthUser,
  LoginRequest,
  LoginResponseDto,
  SignupRequest,
  SignupResponseDto,
} from "@/features/auth/model";

/** 로그인 응답(docs/api-contract.md AUTH)의 user. 이름은 Pencil 홈 시안(EWfx2)의 인사말과 같다. */
export const authUserMock: AuthUser = { id: 1, name: "김재영" };

/**
 * 목 모드의 기본 계정. 백엔드 예시 계정과 같은 비밀번호를 쓴다.
 * 서버 없이도 성공·실패 두 화면(login, login/error)을 모두 확인하려고 둔 값이다.
 */
export const MOCK_PASSWORD = "qwer1234@";
export const MOCK_TAKEN_EMAIL = "qwer@qwer.com";
/** 목 모드 로그인 화면에 미리 채워 두는 계정(어떤 이메일이든 MOCK_PASSWORD 면 통과한다). 개발 빌드 + auth 목일 때만 쓴다 */
export const MOCK_LOGIN_EMAIL = "test@qwer.com";

type MockAccount = { email: string; password: string; user: AuthUser };

/** 앱이 도는 동안만 유지되는 가입 계정. 목으로도 가입 → 로그인 흐름을 이어서 볼 수 있게 한다. */
const accounts = new Map<string, MockAccount>();

function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

function findAccount(email: string, password: string): MockAccount | null {
  const account = accounts.get(normalizeEmail(email));
  if (account !== undefined) return account.password === password ? account : null;
  return password === MOCK_PASSWORD ? { email, password, user: authUserMock } : null;
}

export function loginMock({ email, password }: LoginRequest): LoginResponseDto {
  const account = findAccount(email, password);
  if (account === null) {
    throw new ApiError(401, "AUTH_001", "이메일 또는 비밀번호가 올바르지 않습니다.");
  }
  return {
    accessToken: "mock.access.token",
    refreshToken: "mock.refresh.token",
    user: account.user,
  };
}

/** 테스트·개발 재시작용: 가입 기록을 비운다 */
export function resetAuthMocks(): void {
  accounts.clear();
}

/** 기본 계정 이메일이나 이미 가입한 이메일이면 서버와 같은 USER_002 가 난다. */
export function signupMock({ email, password, name }: SignupRequest): SignupResponseDto {
  const key = normalizeEmail(email);
  if (key === MOCK_TAKEN_EMAIL || accounts.has(key)) {
    throw new ApiError(409, "USER_002", "이미 사용 중인 이메일입니다.");
  }
  const userId = accounts.size + 2;
  accounts.set(key, { email: key, password, user: { id: userId, name } });
  return { userId };
}

/**
 * DELETE /users/me 목. 서버처럼 현재 비밀번호를 확인하고 틀리면 401 USER_007 이다.
 * 목은 어떤 이메일이든 MOCK_PASSWORD 로 로그인되므로 가입해 둔 계정의 비밀번호도 함께 받는다.
 * 탈퇴 이메일 재가입 차단은 서버 몫이라 목에서는 흉내 내지 않는다.
 */
export function deleteAccountMock({ password }: AccountDeletionRequest): void {
  if (password === "") throw new ApiError(400, "COMMON_001", "비밀번호를 입력해 주세요.");
  const known = password === MOCK_PASSWORD || [...accounts.values()].some((account) => account.password === password);
  if (!known) throw new ApiError(401, "USER_007", "현재 비밀번호가 올바르지 않습니다.");
}
