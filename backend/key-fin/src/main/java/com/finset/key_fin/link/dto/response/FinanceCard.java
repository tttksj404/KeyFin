package com.finset.key_fin.link.dto.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceCard(
		String cardNo,
		String cvc,
		String cardUniqueNo,
		String cardIssuerCode,
		String cardIssuerName,
		String cardName,
		String cardExpiryDate,
		String withdrawalAccountNo,
		String withdrawalDate
) {

	public int withdrawalWeekday() {
		return Integer.parseInt(withdrawalDate);
	}

	@Override
	public String toString() {
		return "FinanceCard[cardNo=" + maskCardNo()
				+ ", cvc=***"
				+ ", cardIssuerCode=" + cardIssuerCode
				+ ", cardIssuerName=" + cardIssuerName
				+ ", cardName=" + cardName
				+ ", withdrawalAccountNo=" + withdrawalAccountNo + "]";
	}

	private String maskCardNo() {
		if (cardNo == null || cardNo.length() < 4) {
			return "****";
		}
		return "****" + cardNo.substring(cardNo.length() - 4);
	}
}
