import { unwrapEnvelope } from "@/api/envelope";
import { ApiError, NETWORK_ERROR_CODE, toApiError } from "@/api/error";

describe("unwrapEnvelope", () => {
  it("공통 봉투는 data 만 남긴다", () => {
    expect(unwrapEnvelope({ success: true, code: "SUCCESS", message: "요청이 성공했습니다.", data: { userId: 1 } })).toEqual({
      userId: 1,
    });
  });

  it("본문 없는 성공(data: null)은 null 이 된다", () => {
    expect(unwrapEnvelope({ success: true, code: "SUCCESS", message: "요청이 성공했습니다.", data: null })).toBeNull();
  });

  it("커서 목록도 봉투 안에 그대로 들어 있다", () => {
    const page = { items: [{ id: 1 }], nextCursor: null };
    expect(unwrapEnvelope({ success: true, code: "SUCCESS", message: "", data: page })).toEqual(page);
  });

  it("봉투가 아닌 본문은 그대로 둔다", () => {
    expect(unwrapEnvelope({ month: "202609" })).toEqual({ month: "202609" });
    expect(unwrapEnvelope(null)).toBeNull();
  });
});

describe("toApiError", () => {
  it("오류 봉투의 code·message 를 그대로 옮긴다", () => {
    const error = toApiError(401, { success: false, code: "AUTH_001", message: "이메일 또는 비밀번호가 올바르지 않습니다.", data: null });
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
    expect(error.code).toBe("AUTH_001");
    expect(error.message).toBe("이메일 또는 비밀번호가 올바르지 않습니다.");
  });

  it("code·message 가 없으면 기본값을 쓴다", () => {
    expect(toApiError(500, null).code).toBe("UNKNOWN");
    expect(toApiError(0, null, NETWORK_ERROR_CODE).message).toBe("네트워크에 연결할 수 없어요.");
  });
});
