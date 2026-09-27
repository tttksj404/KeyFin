package com.finset.key_fin.transaction.dto.finance.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceCardTransaction(
		String transactionUniqueNo,
		String categoryId,
		String categoryName,
		Long merchantId,
		String merchantName,
		String transactionDate,
		String transactionTime,
		Long transactionBalance,
		String cardStatus,
		String billStatementsYn,
		String billStatementsStatus
) {
}
