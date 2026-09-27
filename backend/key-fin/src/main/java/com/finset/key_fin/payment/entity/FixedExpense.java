package com.finset.key_fin.payment.entity;

import java.time.LocalDate;
import java.time.YearMonth;

import com.finset.key_fin.user.entity.User;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "fixed_expenses")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class FixedExpense {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@Column(nullable = false, length = 50)
	private String name;

	@Enumerated(EnumType.STRING)
	@Column(name = "expense_type", nullable = false, length = 20)
	private ExpenseType expenseType;

	@Column
	private Long amount;

	@Column(name = "is_variable", nullable = false)
	private boolean variable;

	@Column(name = "payment_day", nullable = false)
	private int paymentDay;

	@Column(name = "withdrawal_account_id")
	private Long withdrawalAccountId;

	@Column(name = "card_id")
	private Long cardId;

	@Column(name = "fin_subscription_id", length = 30)
	private String finSubscriptionId;

	@Column(nullable = false)
	private boolean active = true;

	public static FixedExpense register(User user, String name, ExpenseType expenseType, long amount,
			boolean variable, int paymentDay, long withdrawalAccountId) {
		FixedExpense expense = new FixedExpense();
		expense.user = user;
		expense.update(name, expenseType, amount, variable, paymentDay, withdrawalAccountId);
		return expense;
	}

	public static FixedExpense sync(User user, String finSubscriptionId, String name, long amount, int paymentDay) {
		FixedExpense expense = new FixedExpense();
		expense.user = user;
		expense.finSubscriptionId = finSubscriptionId;
		expense.expenseType = ExpenseType.SUBSCRIPTION;
		expense.variable = false;
		expense.syncFrom(name, amount, paymentDay);
		return expense;
	}

	public void syncFrom(String name, long amount, int paymentDay) {
		this.name = name;
		this.amount = amount;
		this.paymentDay = paymentDay;
		this.active = true;
	}

	public void update(String name, ExpenseType expenseType, long amount, boolean variable, int paymentDay,
			long withdrawalAccountId) {
		this.name = name;
		this.expenseType = expenseType;
		this.amount = amount;
		this.variable = variable;
		this.paymentDay = paymentDay;
		this.withdrawalAccountId = withdrawalAccountId;
	}

	public void assignCard(long cardId) {
		this.cardId = cardId;
	}

	public void deactivate() {
		this.active = false;
	}

	public boolean isSynced() {
		return finSubscriptionId != null;
	}

	public LocalDate paymentDateIn(YearMonth month) {
		return month.atDay(Math.min(paymentDay, month.lengthOfMonth()));
	}
}
