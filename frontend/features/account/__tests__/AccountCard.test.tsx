import { fireEvent, render, screen } from "@testing-library/react-native";
import * as React from "react";

import { AccountCard } from "@/features/account/components/AccountCard";
import type { AccountSummary } from "@/features/account/model";

const account: AccountSummary = {
  accountId: "acc_001",
  bankName: "하네스은행",
  alias: "생활비 통장",
  maskedAccountNumber: "110-***-**6789",
  balance: "3469520",
};

function Harness() {
  const [hidden, setHidden] = React.useState(false);
  return <AccountCard account={account} balanceHidden={hidden} onToggleBalanceHidden={() => setHidden((h) => !h)} />;
}

describe("AccountCard", () => {
  it("마스킹된 계좌번호와 포맷된 잔액을 표시한다", async () => {
    await render(<Harness />);
    expect(screen.getByText("110-***-**6789")).toBeTruthy();
    expect(screen.getByText("3,469,520원")).toBeTruthy();
    expect(screen.getByText("생활비 통장")).toBeTruthy();
  });

  it("숨김 토글을 누르면 잔액을 가리고 라벨이 바뀐다", async () => {
    await render(<Harness />);
    await fireEvent.press(screen.getByRole("button", { name: "잔액 숨기기" }));
    expect(screen.getByLabelText("잔액 숨김")).toBeTruthy();
    expect(screen.queryByText("3,469,520원")).toBeNull();

    await fireEvent.press(screen.getByRole("button", { name: "잔액 보기" }));
    expect(screen.getByText("3,469,520원")).toBeTruthy();
  });
});
