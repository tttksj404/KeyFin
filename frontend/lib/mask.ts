export type MaskOptions = {
  visibleStart?: number;
  visibleEnd?: number;
  maskChar?: string;
};

const DIGIT = /\d/;

export function maskDigits(
  value: string,
  { visibleStart = 0, visibleEnd = 0, maskChar = "*" }: MaskOptions = {}
): string {
  const total = value.replace(/\D/g, "").length;
  const start = total > visibleStart + visibleEnd ? visibleStart : 0;
  const end = total > visibleEnd ? visibleEnd : 0;

  let index = 0;
  let masked = "";
  for (const char of value) {
    if (!DIGIT.test(char)) {
      masked += char;
      continue;
    }
    const visible = index < start || index >= total - end;
    masked += visible ? char : maskChar;
    index += 1;
  }
  return masked;
}

export function maskAccount(accountNumber: string): string {
  return maskDigits(accountNumber, { visibleStart: 3, visibleEnd: 4 });
}

export function maskCardNumber(cardNumber: string): string {
  return maskDigits(cardNumber, { visibleStart: 4, visibleEnd: 4 });
}

export function maskPhone(phoneNumber: string): string {
  return maskDigits(phoneNumber, { visibleStart: 3, visibleEnd: 4 });
}

export function maskResidentNumber(residentNumber: string): string {
  return maskDigits(residentNumber, { visibleStart: 7 });
}
