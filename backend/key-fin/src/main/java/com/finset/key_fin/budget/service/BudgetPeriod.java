package com.finset.key_fin.budget.service;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

public record BudgetPeriod(String month, LocalDate from, LocalDate to) {

	private static final DateTimeFormatter MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");

	public static BudgetPeriod of(String month, int anchorDay) {
		LocalDate from = LocalDate.parse(month + "01", DateTimeFormatter.BASIC_ISO_DATE)
				.withDayOfMonth(anchorDay);
		return new BudgetPeriod(month, from, from.plusMonths(1));
	}

	public static BudgetPeriod current(LocalDate today, int anchorDay) {
		LocalDate labelDate = today.getDayOfMonth() >= anchorDay ? today : today.minusMonths(1);
		return of(labelDate.format(MONTH_FORMAT), anchorDay);
	}
}
