import { cn } from "@/lib/utils";

describe("cn", () => {
  it("병합 시 뒤의 Tailwind 클래스가 앞의 충돌 클래스를 덮어쓴다", () => {
    expect(cn("bg-card p-4", "bg-background")).toBe("p-4 bg-background");
  });

  it("falsy 값을 무시한다", () => {
    expect(cn("text-foreground", false, undefined, null, "")).toBe("text-foreground");
  });
});

describe("cn — 디자인 토큰 클래스", () => {
  it("타이포 토큰을 색상이 아니라 글자 크기로 인식해 text-foreground를 유지한다", () => {
    expect(cn("text-foreground font-sans text-base", "text-amount-lg tabular-nums")).toBe(
      "text-foreground font-sans text-amount-lg tabular-nums"
    );
  });

  it("타이포 토큰끼리, 색상 토큰끼리 뒤의 값이 이긴다", () => {
    expect(cn("text-amount-md text-foreground", "text-amount-sm text-destructive")).toBe(
      "text-amount-sm text-destructive"
    );
  });

  it("크기 토큰(h-input 등)이 기본 높이 클래스를 덮어쓴다", () => {
    expect(cn("h-10 rounded-md", "h-input")).toBe("rounded-md h-input");
  });
});
