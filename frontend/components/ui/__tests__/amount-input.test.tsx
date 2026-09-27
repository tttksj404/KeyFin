import { fireEvent, render, screen } from "@testing-library/react-native";
import * as React from "react";
import { Text as RNText } from "react-native";

import { AmountInput } from "@/components/ui/amount-input";
import { addKRW } from "@/lib/money";

function Harness({ max, initial = "", editable }: { max?: string; initial?: string; editable?: boolean }) {
  const [value, setValue] = React.useState(initial);
  return (
    <>
      <AmountInput value={value} onChangeValue={setValue} max={max} editable={editable} />
      <MirrorValue value={value} />
    </>
  );
}

function MirrorValue({ value }: { value: string }) {
  return <RNText testID="raw-value">{value}</RNText>;
}

const rawValue = () => screen.getByTestId("raw-value").props.children;
const input = () => screen.getByLabelText("금액");

describe("AmountInput", () => {
  it("붙여넣은 값에서 숫자만 남기고 콤마 포맷으로 표시한다", async () => {
    await render(<Harness />);
    await fireEvent.changeText(input(), "1,000abc");
    expect(rawValue()).toBe("1000");
    expect(input().props.value).toBe("1,000");
  });

  it("선행 0을 제거한다", async () => {
    await render(<Harness />);
    await fireEvent.changeText(input(), "007");
    expect(rawValue()).toBe("7");
  });

  it("숫자 키패드를 지정한다", async () => {
    await render(<Harness />);
    expect(input().props.keyboardType).toBe("number-pad");
    expect(input().props.inputMode).toBe("numeric");
  });

  it("한도 초과 시 오류를 표시하고 입력값은 유지하며, 줄이면 오류가 사라진다", async () => {
    await render(<Harness max="50000" />);
    await fireEvent.changeText(input(), "60000");
    expect(screen.getByText("50,000원까지 입력할 수 있어요")).toBeTruthy();
    expect(rawValue()).toBe("60000");

    await fireEvent.changeText(input(), "50000");
    expect(screen.queryByText("50,000원까지 입력할 수 있어요")).toBeNull();
  });

  it("빠른 금액 칩 누적 합산이 addKRW 결과와 일치한다", async () => {
    await render(<Harness initial="1234" />);
    await fireEvent.press(screen.getByRole("button", { name: "+1만" }));
    await fireEvent.press(screen.getByRole("button", { name: "+5만" }));
    await fireEvent.press(screen.getByRole("button", { name: "+10만" }));
    expect(rawValue()).toBe(addKRW("1234", "10000", "50000", "100000"));
  });

  it("빈 값에서 칩을 누르면 칩 금액이 된다", async () => {
    await render(<Harness />);
    await fireEvent.press(screen.getByRole("button", { name: "+1만" }));
    expect(rawValue()).toBe("10000");
  });

  it("전액 칩은 max가 있을 때만 보이고 누르면 max로 채운다", async () => {
    await render(<Harness />);
    expect(screen.queryByRole("button", { name: "전액" })).toBeNull();

    await screen.unmount();
    await render(<Harness max="1250000" />);
    await fireEvent.press(screen.getByRole("button", { name: "전액" }));
    expect(rawValue()).toBe("1250000");
  });

  it("editable=false면 입력과 칩이 모두 비활성이다", async () => {
    await render(<Harness initial="100" editable={false} />);
    await fireEvent.press(screen.getByRole("button", { name: "+1만" }));
    expect(rawValue()).toBe("100");
    expect(input().props.accessibilityState).toEqual({ disabled: true });
  });
});
