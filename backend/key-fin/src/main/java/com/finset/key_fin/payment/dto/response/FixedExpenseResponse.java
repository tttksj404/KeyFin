package com.finset.key_fin.payment.dto.response;

import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.entity.FixedExpense;

public record FixedExpenseResponse(
		Long id,
		String name,
		ExpenseType expenseType,
		Long amount,
		boolean isVariable,
		int paymentDay,
		Long withdrawalAccountId,
		boolean synced,
		Long cardId
) {

	public static FixedExpenseResponse from(FixedExpense expense) {
		return new FixedExpenseResponse(
				expense.getId(),
				expense.getName(),
				expense.getExpenseType(),
				expense.getAmount(),
				expense.isVariable(),
				expense.getPaymentDay(),
				expense.getWithdrawalAccountId(),
				expense.isSynced(),
				expense.getCardId());
	}
}
