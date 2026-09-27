package com.finset.key_fin.payment.dto.response;

import java.time.LocalDate;
import java.util.List;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.entity.FixedExpense;

public record PaymentCalendarResponse(String month, List<Day> days) {

	public record Day(LocalDate date, List<Item> items) {
	}

	public record Item(
			CalendarItemType type,
			Long fixedExpenseId,
			Long cardId,
			String name,
			ExpenseType expenseType,
			long amount,
			boolean estimated,
			Long withdrawalAccountId,
			Boolean prepared,
			Long shortage
	) {
		public static Item of(FixedExpense expense) {
			return new Item(
					expense.isSynced() ? CalendarItemType.CARD_SUBSCRIPTION : CalendarItemType.FIXED,
					expense.getId(),
					null,
					expense.getName(),
					expense.getExpenseType(),
					expense.getAmount(),
					expense.isVariable(),
					expense.getWithdrawalAccountId(),
					null,
					null);
		}

		public static Item of(CardBilling billing, String cardName, Long withdrawalAccountId) {
			boolean paid = billing.isPaid();
			return new Item(
					CalendarItemType.CARD_BILL,
					null,
					billing.getCardId(),
					cardName,
					ExpenseType.CARD_BILL,
					billing.getTotalAmount(),
					false,
					withdrawalAccountId,
					paid ? Boolean.TRUE : null,
					paid ? 0L : null);
		}

		public static Item estimatedCardBill(long cardId, String cardName, long amount, Long withdrawalAccountId) {
			return new Item(
					CalendarItemType.CARD_BILL, null, cardId, cardName, ExpenseType.CARD_BILL, amount, true,
					withdrawalAccountId, null, null);
		}

		public Item judged(boolean prepared, long shortage) {
			return new Item(type, fixedExpenseId, cardId, name, expenseType, amount, estimated, withdrawalAccountId,
					prepared, shortage);
		}
	}

	public enum CalendarItemType {
		FIXED,
		CARD_SUBSCRIPTION,
		CARD_BILL
	}
}
