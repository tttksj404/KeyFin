package com.finset.key_fin.global.finance.dto.request;

public record FinanceRequestHeader(
		String apiName,
		String transmissionDate,
		String transmissionTime,
		String institutionCode,
		String fintechAppNo,
		String apiServiceCode,
		String institutionTransactionUniqueNo,
		String apiKey,
		String userKey
) {

	@Override
	public String toString() {
		return "FinanceRequestHeader[apiName=" + apiName
				+ ", transmissionDate=" + transmissionDate
				+ ", transmissionTime=" + transmissionTime
				+ ", institutionTransactionUniqueNo=" + institutionTransactionUniqueNo
				+ ", apiKey=******, userKey=******]";
	}
}
