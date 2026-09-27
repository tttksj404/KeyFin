package com.finset.key_fin.payment.dto.request;

import com.finset.key_fin.global.finance.dto.request.FinanceRequestHeader;
import com.fasterxml.jackson.annotation.JsonProperty;

public record FinanceTransferRequest(
		@JsonProperty("Header") FinanceRequestHeader header,
		String depositAccountNo,
		String transactionBalance,
		String withdrawalAccountNo,
		String depositTransactionSummary,
		String withdrawalTransactionSummary
) {
}
