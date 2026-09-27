import { ApiError } from "@/api/error";
import { deleteAccountMock, loginMock, MOCK_PASSWORD, MOCK_TAKEN_EMAIL, resetAuthMocks, signupMock } from "@/api/mocks/auth";
import { accountDeletionErrorMessage, authErrorMessage } from "@/features/auth/errors";
import {
  canAgreeToTerms,
  canSubmitAccountDeletion,
  canSubmitLogin,
  canSubmitSignup,
  isValidEmail,
  loginHref,
  parseReturnTo,
  TERMS_ITEMS,
  toAuthSession,
} from "@/features/auth/model";
import { ContractMismatchError } from "@/lib/contract";

const EMAIL = "qwer@qwer.com";

beforeEach(resetAuthMocks);

describe("toAuthSession", () => {
  it("로그인 응답을 토큰과 사용자로 나눈다", () => {
    const session = toAuthSession(loginMock({ email: EMAIL, password: MOCK_PASSWORD }));
    expect(session.accessToken).toBe("mock.access.token");
    expect(session.refreshToken).toBe("mock.refresh.token");
    expect(session.user).toEqual({ id: 1, name: "김재영" });
  });

  it("토큰이 비었거나 사용자 필드가 계약과 다르면 계약 불일치다", () => {
    const dto = loginMock({ email: EMAIL, password: MOCK_PASSWORD });
    expect(() => toAuthSession({ ...dto, accessToken: "" })).toThrow(ContractMismatchError);
    expect(() => toAuthSession({ ...dto, user: { ...dto.user, id: 1.5 } })).toThrow(ContractMismatchError);
  });
});

describe("loginMock", () => {
  it("목 비밀번호가 아니면 서버와 같은 AUTH_001 로 실패한다", () => {
    expect(() => loginMock({ email: EMAIL, password: "wrong" })).toThrow(ApiError);
    try {
      loginMock({ email: EMAIL, password: "wrong" });
    } catch (error) {
      expect((error as ApiError).code).toBe("AUTH_001");
      expect((error as ApiError).status).toBe(401);
    }
  });
});

describe("isValidEmail · canSubmitLogin", () => {
  it("이메일 형식만 보고 비밀번호 규칙은 서버에 맡긴다", () => {
    expect(isValidEmail(EMAIL)).toBe(true);
    expect(isValidEmail(" qwer@qwer.com ")).toBe(true);
    expect(isValidEmail("qwer@qwer")).toBe(false);
    expect(isValidEmail("")).toBe(false);
  });

  it("이메일 형식이 맞고 비밀번호가 비지 않아야 제출할 수 있다", () => {
    expect(canSubmitLogin(EMAIL, "a")).toBe(true);
    expect(canSubmitLogin(EMAIL, "")).toBe(false);
    expect(canSubmitLogin("qwer", "qwer1234@")).toBe(false);
  });
});

describe("authErrorMessage", () => {
  it("확인된 code 는 정해진 문구를, 모르는 code 는 서버 message 를 쓴다", () => {
    expect(authErrorMessage(new ApiError(401, "AUTH_001", "이메일 또는 비밀번호가 올바르지 않습니다."))).toBe(
      "이메일 또는 비밀번호가 올바르지 않습니다."
    );
    expect(authErrorMessage(new ApiError(409, "USER_002", "무시되는 서버 문구"))).toBe("이미 사용 중인 이메일입니다.");
    expect(authErrorMessage(new ApiError(500, "SERVER_999", "서버가 응답하지 않습니다."))).toBe("서버가 응답하지 않습니다.");
  });

  it("ApiError 가 아니면 기본 문구를 쓴다", () => {
    expect(authErrorMessage(new Error("boom"))).toBe("로그인하지 못했어요. 잠시 후 다시 시도해 주세요.");
  });
});

describe("signupMock · canSubmitSignup", () => {
  it("이미 쓰는 이메일이면 서버와 같은 USER_002 로 실패한다", () => {
    expect(() => signupMock({ email: MOCK_TAKEN_EMAIL, password: MOCK_PASSWORD, name: "김싸피" })).toThrow(ApiError);
    try {
      signupMock({ email: MOCK_TAKEN_EMAIL.toUpperCase(), password: MOCK_PASSWORD, name: "김싸피" });
    } catch (error) {
      expect((error as ApiError).code).toBe("USER_002");
      expect((error as ApiError).status).toBe(409);
    }
  });

  it("새 이메일이면 userId 를 돌려주고, 그 계정으로 바로 로그인할 수 있다", () => {
    expect(signupMock({ email: "new@keyfin.com", password: "mypw123!", name: "이싸피" })).toEqual({ userId: 2 });

    const session = toAuthSession(loginMock({ email: "new@keyfin.com", password: "mypw123!" }));
    expect(session.user).toEqual({ id: 2, name: "이싸피" });
    expect(() => loginMock({ email: "new@keyfin.com", password: "틀린비번" })).toThrow(ApiError);
  });

  it("같은 이메일로 다시 가입하면 USER_002 다", () => {
    signupMock({ email: "new@keyfin.com", password: "mypw123!", name: "이싸피" });
    expect(() => signupMock({ email: "NEW@keyfin.com", password: "mypw123!", name: "이싸피" })).toThrow(ApiError);
  });

  it("이름이 공백뿐이면 제출할 수 없다", () => {
    expect(canSubmitSignup("new@keyfin.com", "pw", "김싸피")).toBe(true);
    expect(canSubmitSignup("new@keyfin.com", "pw", "   ")).toBe(false);
    expect(canSubmitSignup("new", "pw", "김싸피")).toBe(false);
  });
});

describe("canAgreeToTerms", () => {
  it("필수 두 개를 모두 체크해야 계속할 수 있다", () => {
    expect(canAgreeToTerms([])).toBe(false);
    expect(canAgreeToTerms(["service"])).toBe(false);
    expect(canAgreeToTerms(["service", "privacy"])).toBe(true);
  });

  it("선택 항목은 계속하기에 영향을 주지 않는다", () => {
    expect(canAgreeToTerms(["marketing"])).toBe(false);
    expect(canAgreeToTerms(["service", "privacy", "marketing"])).toBe(true);
  });

  it("필수는 2개, 선택은 1개다", () => {
    expect(TERMS_ITEMS.filter((item) => item.required)).toHaveLength(2);
    expect(TERMS_ITEMS.filter((item) => !item.required)).toHaveLength(1);
  });
});

describe("loginHref · parseReturnTo (로그인 후 복귀)", () => {
  it("딥링크로 들어온 경로는 returnTo 로 달고, 홈은 그냥 로그인으로 보낸다", () => {
    expect(loginHref("/payment/transfer/501")).toBe("/(auth)/login?returnTo=%2Fpayment%2Ftransfer%2F501");
    expect(loginHref("/")).toBe("/(auth)/login");
  });

  it("앱 밖 주소나 인증 화면은 복귀 대상으로 받지 않는다", () => {
    expect(loginHref("//evil.example.com")).toBe("/(auth)/login");
    expect(loginHref("https://evil.example.com")).toBe("/(auth)/login");
    expect(loginHref("/(auth)/terms")).toBe("/(auth)/login");
  });

  it("returnTo 는 디코딩해 앱 안 경로만 통과시키고 나머지는 홈이다", () => {
    expect(parseReturnTo("%2Ftransaction%2F501")).toBe("/transaction/501");
    expect(parseReturnTo("/my/settings")).toBe("/my/settings");
    expect(parseReturnTo(["/budget/1", "/x"])).toBe("/budget/1");
    expect(parseReturnTo("//evil.example.com")).toBe("/");
    expect(parseReturnTo("https://evil.example.com")).toBe("/");
    expect(parseReturnTo("%E0%A4%A")).toBe("/");
    expect(parseReturnTo(undefined)).toBe("/");
  });
});

describe("회원 탈퇴 (DELETE /users/me)", () => {
  it("비밀번호를 넣어야 보낼 수 있다", () => {
    expect(canSubmitAccountDeletion("")).toBe(false);
    expect(canSubmitAccountDeletion(MOCK_PASSWORD)).toBe(true);
  });

  it("목은 현재 비밀번호를 확인하고 틀리면 401 USER_007 이다", () => {
    resetAuthMocks();
    expect(() => deleteAccountMock({ password: MOCK_PASSWORD })).not.toThrow();

    const codeOf = (run: () => void) => {
      try {
        run();
        return null;
      } catch (error) {
        return error instanceof ApiError ? error.code : "NOT_API_ERROR";
      }
    };
    expect(codeOf(() => deleteAccountMock({ password: "wrong-password" }))).toBe("USER_007");
    expect(codeOf(() => deleteAccountMock({ password: "" }))).toBe("COMMON_001");
    resetAuthMocks();
  });

  it("실패 문구는 비밀번호 불일치와 그 밖을 구분한다", () => {
    expect(accountDeletionErrorMessage(new ApiError(401, "USER_007", ""))).toContain("비밀번호");
    expect(accountDeletionErrorMessage(new ApiError(500, "UNKNOWN_CODE", "서버 문구"))).toBe("서버 문구");
    expect(accountDeletionErrorMessage(new Error("x"))).toContain("탈퇴하지 못했어요");
  });
});
