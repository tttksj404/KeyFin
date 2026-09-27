import { InvalidDateError, currentMonthKey, formatMonthKeyLabel, serverClock, toMonthKey } from "@/lib/date";
import { InvalidAmountError, fromServerWon } from "@/lib/money";

describe("fromServerWon", () => {
  it("서버의 원 단위 정수(number)를 KRW 문자열로 바꾼다", () => {
    expect(fromServerWon(1500000)).toBe("1500000");
    expect(fromServerWon(0)).toBe("0");
    expect(fromServerWon(-8000)).toBe("-8000");
  });

  it("소수·문자열·안전 정수 범위 밖 값은 거부한다", () => {
    expect(() => fromServerWon(1.5)).toThrow(InvalidAmountError);
    expect(() => fromServerWon("1000")).toThrow(InvalidAmountError);
    expect(() => fromServerWon(Number.MAX_SAFE_INTEGER + 1)).toThrow(InvalidAmountError);
    expect(() => fromServerWon(Number.NaN)).toThrow(InvalidAmountError);
  });
});

describe("month key", () => {
  it("KST 기준 YYYYMM 을 만든다 (UTC 자정 전이라도 KST 로는 다음 달)", () => {
    expect(toMonthKey("2026-08-31T15:30:00Z")).toBe("202609");
    expect(toMonthKey("2026-08-31T14:59:00Z")).toBe("202608");
    expect(toMonthKey("2026-12-31T20:00:00Z")).toBe("202701");
  });

  it("현재 월은 서버 시각 보정을 따른다", () => {
    const original = serverClock.offsetMs();
    serverClock.sync(new Date("2026-03-01T00:00:00+09:00").toUTCString());
    expect(currentMonthKey()).toBe("202603");
    serverClock.sync(new Date(Date.now() + original).toUTCString());
  });

  it("YYYYMM 을 'N월' 로 표시하고 형식이 틀리면 거부한다", () => {
    expect(formatMonthKeyLabel("202609")).toBe("9월");
    expect(formatMonthKeyLabel("202612")).toBe("12월");
    expect(() => formatMonthKeyLabel("2026-09")).toThrow(InvalidDateError);
    expect(() => formatMonthKeyLabel("202613")).toThrow(InvalidDateError);
  });
});
