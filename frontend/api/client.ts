import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { unwrapEnvelope } from "@/api/envelope";
import { NETWORK_ERROR_CODE, TIMEOUT_ERROR_CODE, toApiError } from "@/api/error";
import { clearTokens, getAccessTokenSync, getRefreshToken, saveTokens } from "@/lib/session-storage";

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "";
export const API_PREFIX = "/api/v1";

/** 통신 도메인. features/<domain> 폴더 이름과 같다 (settings 는 계약상 USER 도메인이다) */
export const API_DOMAINS = [
  "auth",
  "settings",
  "link",
  "account",
  "transaction",
  "budget",
  "payment",
  "room",
  "shop",
  "notification",
  "coaching",
] as const;
export type ApiDomain = (typeof API_DOMAINS)[number];

const LIVE_ALL = "all";

/**
 * 실서버로 보낼 도메인 집합 (docs/api-guide.md §9).
 * 백엔드가 도메인별로 배포되는 동안 "AUTH 는 실서버, 거래는 목" 처럼 섞어 쓰려고 둔다.
 *
 * - 호스트가 비어 있으면 무엇도 실서버가 아니다 → 전부 목
 * - 호스트만 있으면 기존처럼 전부 실서버
 * - `EXPO_PUBLIC_LIVE_DOMAINS` 에 적으면 그 도메인만 실서버고 나머지는 목 (`all` 은 전부)
 */
export function resolveLiveDomains(apiBaseUrl: string, rawLiveDomains: string | undefined): ReadonlySet<ApiDomain> {
  if (apiBaseUrl === "") return new Set();
  const listed = (rawLiveDomains ?? "")
    .split(",")
    .map((name) => name.trim().toLowerCase())
    .filter((name) => name !== "");
  if (listed.length === 0 || listed.includes(LIVE_ALL)) return new Set(API_DOMAINS);
  return new Set(API_DOMAINS.filter((domain) => listed.includes(domain)));
}

const LIVE_DOMAINS = resolveLiveDomains(API_BASE_URL, process.env.EXPO_PUBLIC_LIVE_DOMAINS);

/** 이 도메인은 api/mocks 값을 돌려줄지. 도메인 API 함수가 첫 줄에서 확인한다 */
export function isMocked(domain: ApiDomain): boolean {
  return !LIVE_DOMAINS.has(domain);
}
export const TIMEOUT_QUERY_MS = 10_000;
export const TIMEOUT_MONEY_MS = 30_000;

/** Bearer 를 붙이지 않는 경로 (docs/api-contract.md §1). 로그아웃은 Access Token 이 필요하다. */
const AUTH_FREE_PATHS = ["/auth/signup", "/auth/login", "/auth/refresh"];

function isAuthFree(url: string | undefined): boolean {
  return url !== undefined && AUTH_FREE_PATHS.some((path) => url.startsWith(path));
}

/**
 * 공용 axios 인스턴스. 도메인 API 함수(features/<domain>/api)만 이 인스턴스를 호출한다.
 * 경로는 `/api/v1` 을 뺀 값만 넘긴다 (`api.get("/room")`).
 */
export const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: TIMEOUT_QUERY_MS,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

/** 토큰 재발급 전용. 인터셉터가 붙지 않아 401 재귀를 만들지 않는다. */
const refreshClient = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: TIMEOUT_QUERY_MS,
  headers: { Accept: "application/json", "Content-Type": "application/json" },
});

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

/** 갱신 실패로 세션이 끝났을 때 앱이 로그인 화면으로 보내도록 등록하는 자리 (api 층이 라우터를 직접 알지 않는다). */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

/** 동시에 터진 401 이 갱신을 여러 번 호출하지 않도록 하나의 Promise 를 공유한다. */
let refreshPromise: Promise<string> | null = null;

async function requestNewAccessToken(): Promise<string> {
  const refreshToken = await getRefreshToken();
  if (refreshToken === null) throw new Error("no refresh token");

  const { data } = await refreshClient.post("/auth/refresh", { refreshToken });
  const payload = unwrapEnvelope(data) as { accessToken?: unknown };
  if (typeof payload?.accessToken !== "string") throw new Error("invalid refresh response");

  await saveTokens({ accessToken: payload.accessToken });
  return payload.accessToken;
}

function refreshAccessToken(): Promise<string> {
  refreshPromise ??= requestNewAccessToken().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

api.interceptors.request.use((config) => {
  const token = getAccessTokenSync();
  if (token !== null && !isAuthFree(config.url)) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    response.data = unwrapEnvelope(response.data);
    return response;
  },
  async (error: AxiosError) => {
    if (error.response === undefined) {
      const code = error.code === "ECONNABORTED" ? TIMEOUT_ERROR_CODE : NETWORK_ERROR_CODE;
      throw toApiError(0, null, code);
    }

    const { status, data } = error.response;
    const config = error.config as RetriableConfig | undefined;
    const canRetry = status === 401 && config !== undefined && config._retried !== true && !isAuthFree(config.url);

    if (canRetry) {
      try {
        const accessToken = await refreshAccessToken();
        config._retried = true;
        config.headers.Authorization = `Bearer ${accessToken}`;
        return await api.request(config);
      } catch {
        await clearTokens();
        onUnauthorized?.();
      }
    }

    throw toApiError(status, data);
  }
);
