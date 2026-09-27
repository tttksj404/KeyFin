package com.finset.key_fin.transaction.dto.finance.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.finset.key_fin.global.finance.dto.request.FinanceRequestHeader;

public record FinanceCardTransactionRequest(
		@JsonProperty("Header") FinanceRequestHeader header,
		String cardNo,
		String cvc,
		String startDate,
		String endDate
) {
	@Override
	public String toString() {
		return "FinanceCardTransactionRequest[header=" + header
				+ ", cardNo=" + maskCardNo()
				+ ", cvc=***"
				+ ", startDate=" + startDate
				+ ", endDate=" + endDate + "]";
	}

	private String maskCardNo() {
		if (cardNo == null || cardNo.length() < 4) {
			return "****";
		}
		return "****" + cardNo.substring(cardNo.length() - 4);
	}
}
