import { API_DOMAINS, resolveLiveDomains } from "@/api/client";

const URL = "https://api.example.com";

describe("resolveLiveDomains (도메인별 목 스위치)", () => {
  it("서버 주소가 없으면 어떤 도메인도 실서버가 아니다", () => {
    expect(resolveLiveDomains("", undefined).size).toBe(0);
    expect(resolveLiveDomains("", "auth,link").size).toBe(0);
  });

  it("주소만 있으면 기존처럼 전부 실서버다", () => {
    expect(resolveLiveDomains(URL, undefined).size).toBe(API_DOMAINS.length);
    expect(resolveLiveDomains(URL, "  ").size).toBe(API_DOMAINS.length);
    expect(resolveLiveDomains(URL, "all").size).toBe(API_DOMAINS.length);
  });

  it("목록을 적으면 그 도메인만 실서버고 나머지는 목이다", () => {
    const live = resolveLiveDomains(URL, "auth, link ,ACCOUNT");

    expect([...live].sort()).toEqual(["account", "auth", "link"]);
    expect(live.has("transaction")).toBe(false);
    expect(live.has("payment")).toBe(false);
  });

  it("모르는 이름은 무시한다 — 오타로 없는 엔드포인트를 때리지 않게", () => {
    const live = resolveLiveDomains(URL, "auth,transactions,gam");

    expect([...live]).toEqual(["auth"]);
  });
});
