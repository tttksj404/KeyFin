package com.finset.key_fin.transaction.dto.finance.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.finset.key_fin.global.finance.dto.request.FinanceRequestHeader;

public record FinanceAccountTransactionRequest(
		@JsonProperty("Header") FinanceRequestHeader header,
		String accountNo,
		String startDate,
		String endDate,
		String transactionType,
		String orderByType
) {
}
