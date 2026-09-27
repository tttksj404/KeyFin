package com.finset.key_fin.budget.entity;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

class BudgetAlertLevelTest {

	private static final long BUDGET = 100_000L;

	static List<Object[]> 잔액과_기대_단계() {
		return List.of(
				new Object[] {100_000L, BudgetAlertLevel.NONE},
				new Object[] {51_000L, BudgetAlertLevel.NONE},
				new Object[] {50_999L, BudgetAlertLevel.REMAINING_50},
				new Object[] {50_000L, BudgetAlertLevel.REMAINING_50},
				new Object[] {21_000L, BudgetAlertLevel.REMAINING_50},
				new Object[] {20_999L, BudgetAlertLevel.REMAINING_20},
				new Object[] {20_000L, BudgetAlertLevel.REMAINING_20},
				new Object[] {6_000L, BudgetAlertLevel.REMAINING_20},
				new Object[] {5_999L, BudgetAlertLevel.REMAINING_5},
				new Object[] {5_000L, BudgetAlertLevel.REMAINING_5},
				new Object[] {0L, BudgetAlertLevel.REMAINING_5},
				new Object[] {-1L, BudgetAlertLevel.EXCEEDED},
				new Object[] {-50_000L, BudgetAlertLevel.EXCEEDED}
		);
	}

	@ParameterizedTest(name = "잔액 {0} → {1}")
	@MethodSource("잔액과_기대_단계")
	void 잔액에_따라_단계를_판정한다(long remaining, BudgetAlertLevel expected) {
		assertThat(BudgetAlertLevel.of(BUDGET, remaining)).isEqualTo(expected);
	}

	@Test
	void 확정액이_없거나_0이면_판정하지_않는다() {
		assertThat(BudgetAlertLevel.of(null, 10_000L)).isNull();
		assertThat(BudgetAlertLevel.of(0L, 0L)).isNull();
		assertThat(BudgetAlertLevel.of(-1L, 0L)).isNull();
	}

	@Test
	void 잔여율은_내림으로_계산한다() {
		assertThat(BudgetAlertLevel.of(3L, 1L)).isEqualTo(BudgetAlertLevel.REMAINING_50);
	}

	@Test
	void 선언_순서가_심각도다() {
		assertThat(BudgetAlertLevel.EXCEEDED.isWorseThan(BudgetAlertLevel.REMAINING_5)).isTrue();
		assertThat(BudgetAlertLevel.REMAINING_5.isWorseThan(BudgetAlertLevel.REMAINING_20)).isTrue();
		assertThat(BudgetAlertLevel.REMAINING_20.isWorseThan(BudgetAlertLevel.REMAINING_50)).isTrue();
		assertThat(BudgetAlertLevel.REMAINING_50.isWorseThan(BudgetAlertLevel.NONE)).isTrue();
		assertThat(BudgetAlertLevel.NONE.isWorseThan(BudgetAlertLevel.NONE)).isFalse();
		assertThat(BudgetAlertLevel.REMAINING_50.isWorseThan(BudgetAlertLevel.EXCEEDED)).isFalse();
	}

	@Test
	void 초과만_행동이_필요하다() {
		assertThat(BudgetAlertLevel.EXCEEDED.requiresAction()).isTrue();
		assertThat(BudgetAlertLevel.REMAINING_5.requiresAction()).isFalse();
	}
}
