package com.finset.key_fin.payment.entity;

public enum ExpenseType {
	RENT,
	SUBSCRIPTION,
	UTILITY,
	LOAN,
	CARD_BILL;

	public boolean isManualAllowed() {
		return this != CARD_BILL;
	}
}
