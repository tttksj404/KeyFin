package com.finset.key_fin.payment.dto.response;

import java.util.List;
import com.finset.key_fin.global.finance.dto.response.FinanceResponseHeader;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceBillingStatementsResponse(
		@JsonProperty("Header") FinanceResponseHeader header,
		@JsonProperty("REC") List<Month> rec
) {
	public List<FinanceBillingStatement> statementsOrEmpty() {
		if (rec == null) {
			return List.of();
		}
		return rec.stream()
				.filter(month -> month.billingList() != null)
				.flatMap(month -> month.billingList().stream())
				.toList();
	}

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Month(String billingMonth, List<FinanceBillingStatement> billingList) {
	}
}
