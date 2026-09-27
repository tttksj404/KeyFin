package com.finset.key_fin.link.dto.response;

import com.finset.key_fin.global.finance.dto.response.FinanceResponseHeader;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceAccountListResponse(
		@JsonProperty("Header") FinanceResponseHeader header,
		@JsonProperty("REC") List<FinanceAccount> accounts
) {

	public List<FinanceAccount> accountsOrEmpty() {
		return accounts == null ? List.of() : accounts;
	}
}
