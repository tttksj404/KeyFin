package com.finset.key_fin.global.finance.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;

public record FinanceHeaderRequest(
		@JsonProperty("Header") FinanceRequestHeader header
) {
}
