package com.finset.key_fin.transaction.dto.finance.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.finset.key_fin.global.finance.dto.response.FinanceResponseHeader;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceCardTransactionResponse(
		@JsonProperty("Header") FinanceResponseHeader header,
		@JsonProperty("REC") FinanceCardTransactionRecord record
) {
}
