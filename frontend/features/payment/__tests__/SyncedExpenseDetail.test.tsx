import { notifyManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import * as React from "react";

import { assignFixedExpenseCard, getCardBillings, getFixedExpenses } from "@/features/payment/api/payment.api";
import { FixedExpenseFormScreen } from "@/features/payment/components/FixedExpenseFormScreen";
import type { CardBillings, FixedExpense } from "@/features/payment/model";

jest.mock("@/features/payment/api/payment.api", () => ({
  assignFixedExpenseCard: jest.fn(),
  getCardBillings: jest.fn(),
  getFixedExpenses: jest.fn(),
}));
jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn(), canGoBack: () => true, back: jest.fn() }) }));

notifyManager.setScheduler((callback) => callback());

const netflix: FixedExpense = {
  id: 12,
  name: "넷플릭스",
  expenseType: "SUBSCRIPTION",
  amount: "17000",
  isVariable: false,
  paymentDay: 20,
  withdrawalAccountId: null,
  synced: true,
  cardId: null,
};

const cards: CardBillings = {
  asOf: "2026-09-24",
  cycleFrom: "2026-09-21",
  nextBillingDate: "2026-09-28",
  cards: [
    { cardId: 1, cardName: "신한 Deep Dream 체크", estimatedAmount: "0", approvalCount: 0, estimatedWithdrawalDate: null, statement: null },
    { cardId: 2, cardName: "국민 노리 체크", estimatedAmount: "0", approvalCount: 0, estimatedWithdrawalDate: null, statement: null },
  ],
};

describe("카드 정기결제 상세 — 결제 카드 지정 (-184)", () => {
  afterEach(() => cleanup());

  it("카드를 고르면 새로고침 없이 상세의 결제 카드가 바뀐다", async () => {
    let saved = netflix;
    jest.mocked(getFixedExpenses).mockImplementation(async () => [saved]);
    jest.mocked(getCardBillings).mockResolvedValue(cards);
    jest.mocked(assignFixedExpenseCard).mockImplementation(async ({ id, cardId }) => {
      saved = { ...saved, cardId };
      return id;
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { gcTime: Infinity } } });

    await render(
      <QueryClientProvider client={client}>
        <FixedExpenseFormScreen route={{ mode: "edit", id: 12 }} />
      </QueryClientProvider>
    );

    await fireEvent.press(await screen.findByRole("button", { name: "결제 카드 미지정" }));
    await fireEvent.press(await screen.findByText("국민 노리 체크"));

    await waitFor(() => expect(screen.getByRole("button", { name: "결제 카드 국민 노리 체크" })).toBeTruthy());
    expect(jest.mocked(assignFixedExpenseCard).mock.calls[0][0]).toEqual({ id: 12, cardId: 2 });
  });
});
