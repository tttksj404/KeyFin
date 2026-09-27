package com.finset.key_fin.payment.entity;

import java.time.LocalDate;
import java.time.LocalDateTime;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "card_billings")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class CardBilling {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "card_id", nullable = false)
	private Long cardId;

	@Column(name = "billing_date", nullable = false)
	private LocalDate billingDate;

	@Column(name = "total_amount", nullable = false)
	private long totalAmount;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 20)
	private BillingStatus status;

	@Column(name = "paid_at")
	private LocalDateTime paidAt;

	public static CardBilling sync(long cardId, LocalDate billingDate, long totalAmount, boolean paid, LocalDateTime paidAt) {
		CardBilling billing = new CardBilling();
		billing.cardId = cardId;
		billing.billingDate = billingDate;
		billing.syncFrom(totalAmount, paid, paidAt);
		return billing;
	}

	public void syncFrom(long totalAmount, boolean paid, LocalDateTime paidAt) {
		this.totalAmount = totalAmount;
		this.status = paid ? BillingStatus.PAID : BillingStatus.UNPAID;
		this.paidAt = paid ? paidAt : null;
	}

	public boolean isPaid() {
		return status == BillingStatus.PAID;
	}

	/** 발행일(월요일) + (출금 요일 − 1), 요일 1=월 … 7=일. */
	public LocalDate withdrawalDate(int withdrawalWeekday) {
		return billingDate.plusDays(withdrawalWeekday - 1L);
	}

	public enum BillingStatus {
		UNPAID,
		PAID
	}
}
