package com.finset.key_fin.payment.dto.response;

import java.util.List;

import com.finset.key_fin.global.finance.dto.response.FinanceResponseHeader;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceSubscriptionListResponse(
		@JsonProperty("Header") FinanceResponseHeader header,
		@JsonProperty("REC") Rec rec
) {

	public List<FinanceSubscription> subscriptionsOrEmpty() {
		return rec == null || rec.subscriptions() == null ? List.of() : rec.subscriptions();
	}

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Rec(
			String totalMonthlyAmount,
			String activeCount,
			List<FinanceSubscription> subscriptions
	) {
	}
}
