package com.finset.key_fin.transaction.dto.finance.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceAccountTransaction(
		String transactionUniqueNo,
		String transactionDate,
		String transactionTime,
		String transactionType,
		String transactionTypeName,
		String transactionAccountNo,
		Long transactionBalance,
		Long transactionAfterBalance,
		String transactionSummary,
		String transactionMemo
) {
}
