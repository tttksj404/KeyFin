import {
  InvalidDateError,
  createServerClock,
  formatDate,
  formatDateGroupLabel,
  formatDateTime,
  formatMonthDay,
  formatTime,
  getKSTParts,
  parseISODate,
  parseKSTDateKey,
  parseKSTLocalDateTime,
  toKSTDateKey,
} from "@/lib/date";

const UTC_NIGHT = "2026-08-29T20:30:15Z";

describe("parseISODate", () => {
  it("시간대가 포함된 ISO-8601만 허용한다", () => {
    expect(parseISODate(UTC_NIGHT)?.toISOString()).toBe("2026-08-29T20:30:15.000Z");
    expect(parseISODate("2026-08-30T05:30:15+09:00")?.toISOString()).toBe("2026-08-29T20:30:15.000Z");
    expect(parseISODate("2026-08-30T05:30:15.123456+0900")).not.toBeNull();
    expect(parseISODate("2026-08-29T20:30:15")).toBeNull();
    expect(parseISODate("2026-08-29")).toBeNull();
    expect(parseISODate("2026-13-01T00:00:00Z")).toBeNull();
    expect(parseISODate(1756499415000)).toBeNull();
    expect(parseISODate(undefined)).toBeNull();
  });
});

describe("KST 변환", () => {
  it("UTC 시각을 KST(+09:00)로 바꿔 날짜가 넘어가는 경우를 처리한다", () => {
    expect(getKSTParts(UTC_NIGHT)).toEqual({
      year: 2026,
      month: 8,
      day: 30,
      hour: 5,
      minute: 30,
      second: 15,
      weekday: 0,
    });
  });

  it("표시 포맷", () => {
    expect(formatDate(UTC_NIGHT)).toBe("2026.08.30");
    expect(formatTime(UTC_NIGHT)).toBe("05:30");
    expect(formatDateTime(UTC_NIGHT)).toBe("2026.08.30 05:30");
    expect(formatMonthDay(UTC_NIGHT)).toBe("8월 30일 (일)");
    expect(toKSTDateKey(UTC_NIGHT)).toBe("2026-08-30");
  });

  it("Date 객체도 받는다", () => {
    expect(formatDate(new Date(UTC_NIGHT))).toBe("2026.08.30");
  });

  it("서버의 날짜만 있는 값(YYYY-MM-DD)은 KST 자정으로 읽는다", () => {
    expect(formatMonthDay(parseKSTDateKey("2026-09-08"))).toBe("9월 8일 (화)");
    expect(toKSTDateKey(parseKSTDateKey("2026-09-01"))).toBe("2026-09-01");
    expect(() => parseKSTDateKey("2026-09-08T00:00:00")).toThrow(InvalidDateError);
    expect(() => parseKSTDateKey("9월 8일")).toThrow(InvalidDateError);
  });

  it("서버의 시간대 없는 일시(LocalDateTime)는 KST 로 읽고 소수점 초도 받는다", () => {
    expect(formatDateTime(parseKSTLocalDateTime("2026-09-11T14:30:00"))).toBe("2026.09.11 14:30");
    expect(formatTime(parseKSTLocalDateTime("2026-09-11T14:30:05.123456"))).toBe("14:30");
    expect(() => parseKSTLocalDateTime("2026-09-11T14:30:00Z")).toThrow(InvalidDateError);
    expect(() => parseKSTLocalDateTime("2026-09-11")).toThrow(InvalidDateError);
  });

  it("잘못된 값이면 InvalidDateError를 던진다", () => {
    expect(() => formatDate("어제")).toThrow(InvalidDateError);
    expect(() => formatDate(new Date(Number.NaN))).toThrow(InvalidDateError);
  });
});

describe("createServerClock", () => {
  it("응답 Date 헤더로 기기 시각 오프셋을 보정한다", () => {
    let device = Date.UTC(2026, 7, 30, 0, 0, 0);
    const clock = createServerClock(() => device);

    expect(clock.offsetMs()).toBe(0);
    clock.sync("Sun, 30 Aug 2026 00:05:00 GMT");
    expect(clock.offsetMs()).toBe(5 * 60 * 1000);
    expect(clock.now().toISOString()).toBe("2026-08-30T00:05:00.000Z");

    device += 1000;
    expect(clock.now().toISOString()).toBe("2026-08-30T00:05:01.000Z");
  });

  it("파싱할 수 없는 헤더는 무시한다", () => {
    const clock = createServerClock(() => 0);
    clock.sync("invalid");
    expect(clock.offsetMs()).toBe(0);
  });
});

describe("formatDateGroupLabel", () => {
  it("오늘 · 어제 · 월일(요일)로 쓰고, 달이 바뀌어도 어제를 맞춘다", () => {
    expect(formatDateGroupLabel("2026-09-17", "2026-09-17")).toBe("오늘");
    expect(formatDateGroupLabel("2026-09-16", "2026-09-17")).toBe("어제");
    expect(formatDateGroupLabel("2026-09-14", "2026-09-17")).toBe("9월 14일 (월)");
    expect(formatDateGroupLabel("2026-08-31", "2026-09-01")).toBe("어제");
  });
});

