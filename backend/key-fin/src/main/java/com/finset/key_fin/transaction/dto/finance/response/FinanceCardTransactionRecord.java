package com.finset.key_fin.transaction.dto.finance.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceCardTransactionRecord(
		String cardIssuerCode,
		String cardIssuerName,
		String cardName,
		String cardNo,
		Long estimatedBalance,
		List<FinanceCardTransaction> transactionList
) {
	public List<FinanceCardTransaction> transactionsOrEmpty() {
		return transactionList == null ? List.of() : transactionList;
	}
}
