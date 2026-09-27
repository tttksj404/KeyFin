package com.finset.key_fin.budget.entity;

import com.finset.key_fin.global.base.BaseEntity;
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
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Getter
@Entity
@Table(name = "budgets")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Budget extends BaseEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "budget_month", nullable = false, length = 6)
	private String budgetMonth;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 20)
	private BudgetStatus status = BudgetStatus.PROPOSED;

	@Column(name = "emergency_amount", nullable = false)
	private Long emergencyAmount = 0L;

	public static Budget propose(User user, String budgetMonth) {
		Budget budget = new Budget();
		budget.user = user;
		budget.budgetMonth = budgetMonth;
		return budget;
	}

	public boolean isConfirmed() {
		return status == BudgetStatus.CONFIRMED;
	}

	public void confirm() {
		this.status = BudgetStatus.CONFIRMED;
	}

	/** 0 = 미설정(해제). 확정 여부와 무관하게 주기 중 언제든 바꿀 수 있다. */
	public void updateEmergencyAmount(long amount) {
		if (amount < 0) {
			throw new IllegalArgumentException("emergencyAmount must not be negative");
		}
		this.emergencyAmount = amount;
	}
}
