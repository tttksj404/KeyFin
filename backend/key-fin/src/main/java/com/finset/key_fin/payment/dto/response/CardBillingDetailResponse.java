package com.finset.key_fin.payment.dto.response;

import java.time.LocalDate;
import java.util.List;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.Statement;
import com.finset.key_fin.transaction.entity.Transaction;

public record CardBillingDetailResponse(
		LocalDate asOf,
		LocalDate cycleFrom,
		LocalDate nextBillingDate,
		Long cardId,
		String cardName,
		Integer withdrawalWeekday,
		Long withdrawalAccountId,
		EstimatedDetail estimated,
		String from,
		String to,
		List<Statement> statements
) {
	public record EstimatedDetail(long amount, LocalDate withdrawalDate, List<Approval> approvals) {
	}

	public record Approval(Long transactionId, LocalDate date, String merchantName, long amount) {
		public static Approval of(Transaction transaction) {
			return new Approval(transaction.getId(), transaction.getTransactionDate(),
					transaction.getMerchantNameRaw(), transaction.getAmount());
		}
	}
}
