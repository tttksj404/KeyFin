export class InvalidDateError extends Error {
  constructor() {
    super("시각은 시간대가 포함된 ISO-8601 문자열이어야 합니다");
    this.name = "InvalidDateError";
  }
}

const ISO_WITH_ZONE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})$/;
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"] as const;

export type KSTParts = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  weekday: number;
};

export function parseISODate(value: unknown): Date | null {
  if (typeof value !== "string" || !ISO_WITH_ZONE.test(value)) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

const DATE_KEY = /^\d{4}-\d{2}-\d{2}$/;

/**
 * 서버의 날짜 필드("YYYY-MM-DD" — txDate, 결제 캘린더 date)는 시간대가 없는 KST 날짜다.
 * KST 자정(+09:00)을 붙여 읽어 formatMonthDay 등에 넘긴다 (규칙 80: 시간대 없는 값은 +09:00 을 붙여 파싱).
 */
export function parseKSTDateKey(key: string): Date {
  const parsed = DATE_KEY.test(key) ? parseISODate(`${key}T00:00:00+09:00`) : null;
  if (!parsed) throw new InvalidDateError();
  return parsed;
}

/** 시간대 없는 KST 일시. 백엔드 LocalDateTime 은 소수점 초가 붙어 올 수 있다 */
export const KST_LOCAL_DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?$/;

/** 서버의 시간대 없는 일시("YYYY-MM-DDTHH:mm:ss", KST)를 +09:00 을 붙여 읽는다 (규칙 80) */
export function parseKSTLocalDateTime(value: string): Date {
  const parsed = KST_LOCAL_DATE_TIME.test(value) ? parseISODate(`${value}+09:00`) : null;
  if (!parsed) throw new InvalidDateError();
  return parsed;
}

function toDate(value: string | Date): Date {
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) throw new InvalidDateError();
    return value;
  }
  const parsed = parseISODate(value);
  if (!parsed) throw new InvalidDateError();
  return parsed;
}

export function getKSTParts(value: string | Date): KSTParts {
  const shifted = new Date(toDate(value).getTime() + KST_OFFSET_MS);
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes(),
    second: shifted.getUTCSeconds(),
    weekday: shifted.getUTCDay(),
  };
}

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

export function formatDate(value: string | Date): string {
  const { year, month, day } = getKSTParts(value);
  return `${year}.${pad2(month)}.${pad2(day)}`;
}

export function formatTime(value: string | Date): string {
  const { hour, minute } = getKSTParts(value);
  return `${pad2(hour)}:${pad2(minute)}`;
}

export function formatDateTime(value: string | Date): string {
  return `${formatDate(value)} ${formatTime(value)}`;
}

export function formatMonthDay(value: string | Date): string {
  const { month, day, weekday } = getKSTParts(value);
  return `${month}월 ${day}일 (${WEEKDAY_LABELS[weekday]})`;
}

export function toKSTDateKey(value: string | Date): string {
  const { year, month, day } = getKSTParts(value);
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

const MONTH_KEY = /^(\d{4})(0[1-9]|1[0-2])$/;

/** KST 기준 "YYYYMM". 서버 계약의 month 파라미터 형식이다 (docs/api-contract.md §1). */
export function toMonthKey(value: string | Date): string {
  const { year, month } = getKSTParts(value);
  return `${year}${pad2(month)}`;
}

const MONTHS_PER_YEAR = 12;

/** "202609" 을 delta 달만큼 옮긴다. 형식이 틀린 키는 그대로 돌려준다 (거래 내역·결제 캘린더의 월 이동) */
export function shiftMonthKey(key: string, delta: number): string {
  const matched = MONTH_KEY.exec(key);
  if (!matched) return key;
  const index = Number(matched[1]) * MONTHS_PER_YEAR + Number(matched[2]) - 1 + delta;
  return `${Math.floor(index / MONTHS_PER_YEAR)}${String((index % MONTHS_PER_YEAR) + 1).padStart(2, "0")}`;
}

/** 서버 시각 보정을 반영한 이번 달 "YYYYMM" */
export function currentMonthKey(): string {
  return toMonthKey(serverClock.now());
}

/** 서버 시각 보정을 반영한 오늘 "YYYY-MM-DD" */
export function currentDateKey(): string {
  return toKSTDateKey(serverClock.now());
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** 날짜로 묶은 목록의 제목: 오늘 · 어제 · "9월 14일 (월)". todayKey 는 서버 시각 기준 오늘(currentDateKey) */
export function formatDateGroupLabel(dateKey: string, todayKey: string): string {
  if (dateKey === todayKey) return "오늘";
  if (dateKey === toKSTDateKey(new Date(parseKSTDateKey(todayKey).getTime() - DAY_MS))) return "어제";
  return formatMonthDay(parseKSTDateKey(dateKey));
}

/** "202609" → "9월" */
export function formatMonthKeyLabel(key: string): string {
  if (!MONTH_KEY.test(key)) throw new InvalidDateError();
  return `${Number(key.slice(4))}월`;
}

export type ServerClock = {
  sync: (dateHeader: string) => void;
  now: () => Date;
  offsetMs: () => number;
};

export function createServerClock(deviceNow: () => number = Date.now): ServerClock {
  let offset = 0;
  return {
    sync(dateHeader) {
      const serverTime = new Date(dateHeader).getTime();
      if (Number.isNaN(serverTime)) return;
      offset = serverTime - deviceNow();
    },
    now: () => new Date(deviceNow() + offset),
    offsetMs: () => offset,
  };
}

export const serverClock = createServerClock();
