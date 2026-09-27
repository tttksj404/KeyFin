import { api, isMocked } from "@/api/client";
import { deleteAccountMock, loginMock, signupMock } from "@/api/mocks/auth";
import { withMockLatency } from "@/api/mocks/latency";
import {
  toAuthSession,
  type AccountDeletionRequest,
  type AuthSession,
  type LoginRequest,
  type LoginResponseDto,
  type SignupRequest,
  type SignupResponseDto,
} from "@/features/auth/model";

/** POST /auth/login — Access 30분 · Refresh 14일 (docs/api-contract.md AUTH, FR-USR-01). Bearer 불필요. */
export async function login(request: LoginRequest): Promise<AuthSession> {
  if (isMocked("auth")) return toAuthSession(await withMockLatency(loginMock(request)));
  const { data } = await api.post<LoginResponseDto>("/auth/login", request);
  return toAuthSession(data);
}

/**
 * POST /auth/signup — 201 (FR-USR-01). Bearer 불필요.
 * 토큰을 주지 않으므로 가입 뒤에는 로그인 화면으로 보낸다 (유저 플로우 v2 온보딩 레인).
 * 409 USER_002 = 이미 사용 중이거나 탈퇴 이력이 있는 이메일.
 */
export async function signup(request: SignupRequest): Promise<number> {
  if (isMocked("auth")) {
    const { userId } = await withMockLatency(signupMock(request));
    return userId;
  }
  const { data } = await api.post<SignupResponseDto>("/auth/signup", request);
  return data.userId;
}

/**
 * POST /auth/logout — 서버의 Refresh Token 을 지운다. Access Token 이 필요하다.
 * 이미 발급된 Access Token 은 만료까지 유효하므로 호출부가 로컬 토큰도 반드시 지운다.
 * 서버가 실패해도 로컬 세션은 끝내야 하므로 오류를 삼킨다.
 */
export async function logout(): Promise<void> {
  if (isMocked("auth")) {
    await withMockLatency(null);
    return;
  }
  try {
    await api.post("/auth/logout");
  } catch {
    // 서버 상태와 무관하게 로컬 로그아웃은 진행한다
  }
}

/**
 * DELETE /users/me — 회원 탈퇴 (USER 도메인이지만 세션을 끝내는 일이라 auth 에 둔다).
 * 본문에 현재 비밀번호를 담고 성공하면 204(본문 없음)다. 오류: 400 COMMON_001 · 401 USER_007(비밀번호 불일치) · 404 USER_001.
 * 비밀번호는 로그·오류 문맥에 남기지 않는다 (규칙 80).
 */
export async function deleteAccount(request: AccountDeletionRequest): Promise<void> {
  if (isMocked("auth")) {
    await withMockLatency(deleteAccountMock(request));
    return;
  }
  await api.delete("/users/me", { data: request });
}
