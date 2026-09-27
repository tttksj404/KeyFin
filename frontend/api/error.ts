/**
 * 서버 오류를 화면이 다루는 한 가지 형태로 정규화한다 (docs/api-guide.md §3-1).
 * 오류 본문도 성공과 같은 봉투 `{ success: false, code, message, data: null }` 로 온다.
 */
export class ApiError extends Error {
  /** HTTP 상태. 네트워크 단절·타임아웃은 0 */
  readonly status: number;
  /** 봉투의 code. 네트워크 단절은 "NETWORK", 타임아웃은 "TIMEOUT" */
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export const NETWORK_ERROR_CODE = "NETWORK";
export const TIMEOUT_ERROR_CODE = "TIMEOUT";
export const UNKNOWN_ERROR_CODE = "UNKNOWN";

const FALLBACK_MESSAGE = "잠시 후 다시 시도해 주세요.";

const DEFAULT_MESSAGES: Record<string, string> = {
  [NETWORK_ERROR_CODE]: "네트워크에 연결할 수 없어요.",
  [TIMEOUT_ERROR_CODE]: "응답이 너무 늦어요. 다시 시도해 주세요.",
};

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

type ErrorEnvelope = { code?: unknown; message?: unknown };

/** 오류 응답 본문에서 code·message 를 꺼낸다. 봉투가 아니거나 필드가 없으면 기본값을 쓴다. */
export function toApiError(status: number, body: unknown, fallbackCode = UNKNOWN_ERROR_CODE): ApiError {
  const envelope = (body ?? {}) as ErrorEnvelope;
  const code = typeof envelope.code === "string" && envelope.code !== "" ? envelope.code : fallbackCode;
  const message =
    typeof envelope.message === "string" && envelope.message !== ""
      ? envelope.message
      : (DEFAULT_MESSAGES[code] ?? FALLBACK_MESSAGE);
  return new ApiError(status, code, message);
}
