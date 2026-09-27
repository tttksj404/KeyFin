package com.finset.key_fin.budget.entity;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class BudgetTest {

	@Test
	void appliesDatabaseDefaults() {
		Budget budget = new Budget();

		assertThat(budget.getStatus()).isEqualTo(BudgetStatus.PROPOSED);
		assertThat(budget.getEmergencyAmount()).isZero();
	}

	@Test
	void updatesEmergencyAmountRegardlessOfStatusAndRejectsNegative() {
		Budget budget = new Budget();
		budget.confirm();

		budget.updateEmergencyAmount(200000L);
		assertThat(budget.getEmergencyAmount()).isEqualTo(200000L);
		budget.updateEmergencyAmount(0L);
		assertThat(budget.getEmergencyAmount()).isZero();
		assertThatThrownBy(() -> budget.updateEmergencyAmount(-1L)).isInstanceOf(IllegalArgumentException.class);
	}
}
