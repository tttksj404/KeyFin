package com.finset.key_fin.payment.dto.response;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.entity.CardBilling.BillingStatus;

public record CardBillingSummaryResponse(
		LocalDate asOf,
		LocalDate cycleFrom,
		LocalDate nextBillingDate,
		List<CardSummary> cards
) {
	public record CardSummary(
			Long cardId,
			String cardName,
			Integer withdrawalWeekday,
			Long withdrawalAccountId,
			Estimated estimated,
			Statement latestStatement
	) {
	}

	public record Estimated(long amount, int approvalCount, LocalDate withdrawalDate) {
	}

	public record Statement(
			Long billingId,
			LocalDate billingDate,
			long amount,
			BillingStatus status,
			LocalDate withdrawalDate,
			LocalDateTime paidAt
	) {
		public static Statement of(CardBilling billing, Card card) {
			return new Statement(billing.getId(), billing.getBillingDate(), billing.getTotalAmount(), billing.getStatus(),
					card.getWithdrawalWeekday() == null ? null : billing.withdrawalDate(card.getWithdrawalWeekday()),
					billing.getPaidAt());
		}
	}
}
