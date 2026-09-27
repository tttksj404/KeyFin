package com.finset.key_fin.payment.dto.response;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceBillingStatement(
		String billingWeek,
		String billingDate,
		String totalBalance,
		String status,
		String paymentDate,
		String paymentTime
) {
	public static final String STATUS_PAID = "결제완료";
	private static final DateTimeFormatter TIME_FORMAT = DateTimeFormatter.ofPattern("HHmmss");

	public boolean isPaid() {
		return STATUS_PAID.equals(status);
	}

	public long amount() {
		return Long.parseLong(totalBalance);
	}

	public LocalDate issuedOn() {
		return LocalDate.parse(billingDate, DateTimeFormatter.BASIC_ISO_DATE);
	}

	public LocalDateTime paidAt() {
		if (paymentDate == null || paymentDate.isBlank()) {
			return null;
		}
		LocalDate date = LocalDate.parse(paymentDate, DateTimeFormatter.BASIC_ISO_DATE);
		LocalTime time = paymentTime == null || paymentTime.isBlank()
				? LocalTime.MIDNIGHT
				: LocalTime.parse(paymentTime, TIME_FORMAT);
		return LocalDateTime.of(date, time);
	}
}
