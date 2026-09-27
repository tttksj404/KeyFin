export type KRW = string;

export type SignMode = "auto" | "always" | "never";

export class InvalidAmountError extends Error {
  constructor() {
    super("금액은 원 단위 정수 문자열이어야 합니다");
    this.name = "InvalidAmountError";
  }
}

const KRW_PATTERN = /^[+-]?\d+$/;
const KRW_UNIT = "원";

export function isKRW(value: unknown): value is KRW {
  return typeof value === "string" && KRW_PATTERN.test(value);
}

export function toWon(value: KRW): bigint {
  if (!isKRW(value)) throw new InvalidAmountError();
  return BigInt(value);
}

export function fromWon(won: bigint): KRW {
  return won.toString();
}

export function normalizeKRW(value: KRW): KRW {
  return fromWon(toWon(value));
}

/** 서버가 보내는 원 단위 정수(JSON number, 규칙 90)를 KRW 로 바꾼다. 안전 정수가 아니면 InvalidAmountError. */
export function fromServerWon(value: unknown): KRW {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) throw new InvalidAmountError();
  return fromWon(BigInt(value));
}

export function addKRW(...values: KRW[]): KRW {
  return fromWon(values.reduce((sum, value) => sum + toWon(value), 0n));
}

export function subtractKRW(a: KRW, b: KRW): KRW {
  return fromWon(toWon(a) - toWon(b));
}

export function compareKRW(a: KRW, b: KRW): -1 | 0 | 1 {
  const left = toWon(a);
  const right = toWon(b);
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

export function signOfKRW(value: KRW): -1 | 0 | 1 {
  return compareKRW(value, "0");
}

export function isZeroKRW(value: KRW): boolean {
  return signOfKRW(value) === 0;
}

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

type FormatKRWOptions = {
  sign?: SignMode;
  unit?: boolean;
};

export function formatKRW(value: KRW, { sign = "auto", unit = true }: FormatKRWOptions = {}): string {
  const won = toWon(value);
  const magnitude = groupThousands((won < 0n ? -won : won).toString());
  const suffix = unit ? KRW_UNIT : "";

  if (won < 0n) return sign === "never" ? `${magnitude}${suffix}` : `-${magnitude}${suffix}`;
  if (won > 0n && sign === "always") return `+${magnitude}${suffix}`;
  return `${magnitude}${suffix}`;
}

type SanitizeOptions = {
  maxDigits?: number;
};

export function sanitizeAmountInput(raw: string, { maxDigits }: SanitizeOptions = {}): string {
  const digits = raw.replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  return maxDigits === undefined ? digits : digits.slice(0, maxDigits);
}

export function formatAmountInput(digits: string): string {
  if (digits === "") return "";
  return groupThousands(sanitizeAmountInput(digits));
}
