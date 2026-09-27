package com.finset.key_fin.transaction.dto.finance.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceAccountTransactionRecord(
		String totalCount,
		List<FinanceAccountTransaction> list
) {
	public List<FinanceAccountTransaction> transactionsOrEmpty() {
		return list == null ? List.of() : list;
	}
}
