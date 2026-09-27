package com.finset.key_fin.global.finance.client;

public enum FinanceResponseCode {

	SUCCESS("H0000"),
	HEADER_TRANSACTION_NO_DUPLICATED("H1007"),
	HEADER_API_KEY_INVALID("H1008"),
	HEADER_USER_KEY_INVALID("H1009"),
	ACCOUNT_INSUFFICIENT_BALANCE("A1014"),
	TRANSFER_LIMIT_ONCE_EXCEEDED("A1016"),
	TRANSFER_LIMIT_DAILY_EXCEEDED("A1017"),
	MEMBER_NOT_FOUND("E4003"),
	MEMBER_API_KEY_INVALID("E4004"),
	UNKNOWN_ERROR("Q1000");

	private final String code;

	FinanceResponseCode(String code) {
		this.code = code;
	}

	public String code() {
		return code;
	}

	public boolean matches(String responseCode) {
		return code.equals(responseCode);
	}
}
