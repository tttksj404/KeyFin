package com.finset.key_fin.payment.dto.request;

import com.finset.key_fin.global.finance.dto.request.FinanceRequestHeader;
import com.fasterxml.jackson.annotation.JsonProperty;

public record FinanceBillingStatementRequest(
		@JsonProperty("Header") FinanceRequestHeader header,
		String cardNo,
		String cvc,
		String startMonth,
		String endMonth
) {
}
