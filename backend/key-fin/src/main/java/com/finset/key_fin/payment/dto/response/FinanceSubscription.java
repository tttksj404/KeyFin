package com.finset.key_fin.payment.dto.response;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceSubscription(
		String subscriptionId,
		String subscriptionName,
		String paymentAmount,
		String billingCycle,
		String dailyAmount,
		String nextPaymentDate,
		String status
) {

	public static final String CYCLE_MONTHLY = "MONTHLY";
	public static final String STATUS_ACTIVE = "ACTIVE";

	public boolean isMonthly() {
		return CYCLE_MONTHLY.equals(billingCycle);
	}

	public boolean isActive() {
		return STATUS_ACTIVE.equals(status);
	}

	public long amount() {
		return Long.parseLong(paymentAmount);
	}

	public LocalDate nextPayment() {
		return LocalDate.parse(nextPaymentDate, DateTimeFormatter.BASIC_ISO_DATE);
	}
}
