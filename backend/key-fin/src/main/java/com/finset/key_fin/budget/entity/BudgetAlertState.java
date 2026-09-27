package com.finset.key_fin.budget.entity;

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
@Table(name = "budget_alert_states")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class BudgetAlertState {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "budget_id", nullable = false)
	private Long budgetId;

	@Column(name = "envelope_id", nullable = false)
	private Integer envelopeId;

	@Enumerated(EnumType.STRING)
	@Column(name = "last_alert_level", nullable = false, length = 20)
	private BudgetAlertLevel lastAlertLevel = BudgetAlertLevel.NONE;

	public static BudgetAlertState start(long budgetId, int envelopeId, BudgetAlertLevel level) {
		BudgetAlertState state = new BudgetAlertState();
		state.budgetId = budgetId;
		state.envelopeId = envelopeId;
		state.lastAlertLevel = level;
		return state;
	}

	public void moveTo(BudgetAlertLevel level) {
		this.lastAlertLevel = level;
	}
}
