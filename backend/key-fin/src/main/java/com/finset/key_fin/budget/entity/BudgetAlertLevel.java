package com.finset.key_fin.budget.entity;

public enum BudgetAlertLevel {

	NONE,
	REMAINING_50,
	REMAINING_20,
	REMAINING_5,
	EXCEEDED;

	public static BudgetAlertLevel of(Long confirmedAmount, long remaining) {
		if (confirmedAmount == null || confirmedAmount <= 0) {
			return null;
		}
		if (remaining < 0) {
			return EXCEEDED;
		}
		long remainingRate = remaining * 100 / confirmedAmount;
		if (remainingRate <= 5) {
			return REMAINING_5;
		}
		if (remainingRate <= 20) {
			return REMAINING_20;
		}
		return remainingRate <= 50 ? REMAINING_50 : NONE;
	}

	public boolean isWorseThan(BudgetAlertLevel other) {
		return ordinal() > other.ordinal();
	}

	public boolean requiresAction() {
		return this == EXCEEDED;
	}
}
