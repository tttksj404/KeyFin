import { maskAccount, maskCardNumber, maskDigits, maskPhone, maskResidentNumber } from "@/lib/mask";

describe("maskDigits", () => {
  it("구분자는 유지하고 숫자 위치 기준으로 가린다", () => {
    expect(maskDigits("12-3456-78", { visibleStart: 2, visibleEnd: 2 })).toBe("12-****-78");
  });

  it("보이는 자릿수보다 짧으면 앞부분부터 가리고, 끝 자릿수 이하면 전부 가린다", () => {
    expect(maskDigits("1234567", { visibleStart: 3, visibleEnd: 4 })).toBe("***4567");
    expect(maskDigits("1234", { visibleStart: 3, visibleEnd: 4 })).toBe("****");
  });

  it("maskChar를 바꿀 수 있다", () => {
    expect(maskDigits("123456", { visibleEnd: 2, maskChar: "•" })).toBe("••••56");
  });
});

describe("도메인 마스킹", () => {
  it("계좌번호는 앞 3자리·뒤 4자리만 보인다", () => {
    expect(maskAccount("110-123-456789")).toBe("110-***-**6789");
    expect(maskAccount("3333011234567")).toBe("333******4567");
  });

  it("카드번호는 앞 4자리·뒤 4자리만 보인다", () => {
    expect(maskCardNumber("1234-5678-9012-3456")).toBe("1234-****-****-3456");
    expect(maskCardNumber("1234567890123456")).toBe("1234********3456");
  });

  it("전화번호는 앞 3자리·뒤 4자리만 보인다", () => {
    expect(maskPhone("010-1234-5678")).toBe("010-****-5678");
    expect(maskPhone("01012345678")).toBe("010****5678");
  });

  it("주민번호는 생년월일과 뒷자리 첫 숫자만 보인다", () => {
    expect(maskResidentNumber("900101-1234567")).toBe("900101-1******");
  });
});
