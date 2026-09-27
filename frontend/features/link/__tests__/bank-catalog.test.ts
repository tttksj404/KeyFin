import { BANK_CATALOG, CARD_ISSUER_CATALOG, bankInitial, bankLogo, bankLogoByName } from "@/features/link/bank-catalog";

describe("BANK_CATALOG", () => {
  it("금융망 은행 코드 18개를 담는다", () => {
    expect(BANK_CATALOG).toHaveLength(18);
    expect(new Set(BANK_CATALOG.map((bank) => bank.code)).size).toBe(18);
  });

  it("한국은행·싸피은행 말고는 모두 로고가 있다", () => {
    const withoutLogo = BANK_CATALOG.filter((bank) => bank.logo === undefined).map((bank) => bank.code);
    expect(withoutLogo).toEqual(["001", "999"]);
  });

  it("킷에서 심볼을 함께 쓰는 은행은 같은 로고를 가리킨다", () => {
    expect(bankLogo("034")).toBe(bankLogo("037")); // 광주 · 전북
    expect(bankLogo("088")).toBe(bankLogo("035")); // 신한 · 제주
  });
});

describe("bankLogo · bankInitial", () => {
  it("모르는 코드는 로고가 없고 이름 첫 글자를 쓴다", () => {
    expect(bankLogo("777")).toBeUndefined();
    expect(bankInitial("싸피은행")).toBe("싸");
    expect(bankInitial("  ")).toBe("은");
  });
});

describe("bankLogoByName", () => {
  it("카드사 이름을 같은 브랜드의 은행 로고로 잇는다", () => {
    expect(bankLogoByName("신한카드")).toBe(bankLogo("088"));
    expect(bankLogoByName("국민카드")).toBe(bankLogo("004"));
    expect(bankLogoByName("KB국민카드")).toBe(bankLogo("004"));
    expect(bankLogoByName("하나카드")).toBe(bankLogo("081"));
  });

  it("은행이 없는 카드사는 카드사 로고를 쓴다", () => {
    const samsung = CARD_ISSUER_CATALOG.find((issuer) => issuer.name === "삼성카드")?.logo;
    expect(samsung).toBeDefined();
    expect(bankLogoByName("삼성카드")).toBe(samsung);
    expect(bankLogoByName("삼성 카드")).toBe(samsung);
  });

  it("모르는 발급사와 로고 없는 은행은 폴백 타일로 둔다", () => {
    expect(bankLogoByName("싸피카드")).toBeUndefined();
    expect(bankLogoByName("")).toBeUndefined();
  });
});
