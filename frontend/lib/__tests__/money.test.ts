import {
  InvalidAmountError,
  addKRW,
  compareKRW,
  formatAmountInput,
  formatKRW,
  isKRW,
  isZeroKRW,
  normalizeKRW,
  sanitizeAmountInput,
  signOfKRW,
  subtractKRW,
  toWon,
} from "@/lib/money";

describe("isKRW / toWon", () => {
  it("원 단위 정수 문자열만 허용한다", () => {
    expect(isKRW("0")).toBe(true);
    expect(isKRW("-30000")).toBe(true);
    expect(isKRW("+100")).toBe(true);
    expect(isKRW("30000.00")).toBe(false);
    expect(isKRW("1,000")).toBe(false);
    expect(isKRW("")).toBe(false);
    expect(isKRW(30000)).toBe(false);
    expect(isKRW(null)).toBe(false);
  });

  it("number 정밀도를 넘는 금액도 손실 없이 다룬다", () => {
    expect(toWon("9007199254740993")).toBe(9007199254740993n);
  });

  it("잘못된 형식이면 InvalidAmountError를 던지고 메시지에 값을 담지 않는다", () => {
    expect(() => toWon("abc")).toThrow(InvalidAmountError);
    expect(() => toWon("abc")).toThrow(/원 단위 정수/);
    try {
      toWon("12abc");
    } catch (error) {
      expect(error instanceof Error && error.message.includes("12abc")).toBe(false);
    }
  });
});

describe("normalizeKRW / 연산", () => {
  it("부호와 선행 0을 정규화한다", () => {
    expect(normalizeKRW("+0100")).toBe("100");
    expect(normalizeKRW("-0")).toBe("0");
  });

  it("합산·차감 결과를 문자열로 돌려준다", () => {
    expect(addKRW("10000", "50000", "100000")).toBe("160000");
    expect(addKRW()).toBe("0");
    expect(subtractKRW("10000", "30000")).toBe("-20000");
  });

  it("비교와 부호를 판별한다", () => {
    expect(compareKRW("1", "2")).toBe(-1);
    expect(compareKRW("2", "2")).toBe(0);
    expect(compareKRW("3", "2")).toBe(1);
    expect(signOfKRW("-1")).toBe(-1);
    expect(signOfKRW("0")).toBe(0);
    expect(isZeroKRW("-0")).toBe(true);
  });
});

describe("formatKRW", () => {
  it("천 단위 콤마와 원 단위를 붙인다", () => {
    expect(formatKRW("0")).toBe("0원");
    expect(formatKRW("-1")).toBe("-1원");
    expect(formatKRW("1250000")).toBe("1,250,000원");
    expect(formatKRW("123456789012")).toBe("123,456,789,012원");
  });

  it("sign 옵션에 따라 부호를 표시한다", () => {
    expect(formatKRW("30000", { sign: "always" })).toBe("+30,000원");
    expect(formatKRW("0", { sign: "always" })).toBe("0원");
    expect(formatKRW("-30000", { sign: "always" })).toBe("-30,000원");
    expect(formatKRW("-30000", { sign: "never" })).toBe("30,000원");
    expect(formatKRW("-30000")).toBe("-30,000원");
  });

  it("unit: false면 단위를 생략한다", () => {
    expect(formatKRW("1000", { unit: false })).toBe("1,000");
  });
});

describe("sanitizeAmountInput / formatAmountInput", () => {
  it("숫자 외 문자를 제거하고 선행 0을 없앤다", () => {
    expect(sanitizeAmountInput("1,000abc")).toBe("1000");
    expect(sanitizeAmountInput("007")).toBe("7");
    expect(sanitizeAmountInput("000")).toBe("0");
    expect(sanitizeAmountInput("")).toBe("");
    expect(sanitizeAmountInput("-500")).toBe("500");
  });

  it("maxDigits를 넘는 자릿수는 잘라낸다", () => {
    expect(sanitizeAmountInput("123456789", { maxDigits: 5 })).toBe("12345");
  });

  it("입력 표시값은 단위 없이 콤마만 붙인다", () => {
    expect(formatAmountInput("")).toBe("");
    expect(formatAmountInput("1000")).toBe("1,000");
    expect(formatAmountInput("0012345")).toBe("12,345");
  });
});
