package com.finset.key_fin.link.dto.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceAccount(
		String bankCode,
		String bankName,
		String accountNo,
		String accountName,
		String accountTypeCode,
		Long accountBalance,
		String currency
) {

	public static final String DEMAND_DEPOSIT_TYPE_CODE = "1";

	public boolean isDemandDeposit() {
		return DEMAND_DEPOSIT_TYPE_CODE.equals(accountTypeCode);
	}
}
