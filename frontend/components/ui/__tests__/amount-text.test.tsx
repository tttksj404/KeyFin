import { render, screen } from "@testing-library/react-native";

import { AmountText } from "@/components/ui/amount-text";

describe("AmountText", () => {
  it("0원은 부호 없이 기본 색으로 표시한다", async () => {
    await render(<AmountText value="0" sign="always" />);
    const text = screen.getByText("0원");
    expect(text.props.className).toContain("text-foreground");
    expect(text.props.className).toContain("tabular-nums");
  });

  it("음수는 - 부호와 destructive 색으로 표시한다", async () => {
    await render(<AmountText value="-1" size="sm" />);
    const text = screen.getByText("-1원");
    expect(text.props.className).toContain("text-amount-sm");
    expect(text.props.className).toContain("text-destructive");
  });

  it("sign='always'인 양수는 + 부호와 positive 색으로 표시한다", async () => {
    await render(<AmountText value="1250000" size="lg" sign="always" />);
    const text = screen.getByText("+1,250,000원");
    expect(text.props.className).toContain("text-amount-lg");
    expect(text.props.className).toContain("text-positive");
  });

  it("sign='auto'인 양수는 부호 없이 기본 색이다", async () => {
    await render(<AmountText value="123456789012" />);
    const text = screen.getByText("123,456,789,012원");
    expect(text.props.className).toContain("text-foreground");
    expect(text.props.className).not.toContain("text-positive");
  });

  it("hidden이면 금액을 가리고 접근성 라벨을 '잔액 숨김'으로 둔다", async () => {
    await render(<AmountText value="-30000" hidden />);
    const text = screen.getByLabelText("잔액 숨김");
    expect(text.props.children).toBe("••••••원");
    expect(text.props.className).not.toContain("text-destructive");
  });

  it("접근성 라벨은 화면 텍스트와 같고 글꼴 배율 상한을 둔다", async () => {
    await render(<AmountText value="30000" />);
    const text = screen.getByLabelText("30,000원");
    expect(text.props.maxFontSizeMultiplier).toBe(1.3);
  });
});
