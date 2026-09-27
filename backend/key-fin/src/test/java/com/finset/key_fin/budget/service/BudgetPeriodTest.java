package com.finset.key_fin.budget.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class BudgetPeriodTest {

	@Test
	@DisplayName("기준일 1(기본)이면 주기는 달력 월과 동일하다")
	void defaultAnchor() {
		BudgetPeriod period = BudgetPeriod.of("202609", 1);

		assertThat(period.from()).isEqualTo(LocalDate.of(2026, 9, 1));
		assertThat(period.to()).isEqualTo(LocalDate.of(2026, 10, 1));
	}

	@Test
	@DisplayName("기준일 25면 주기는 25일부터 익월 25일 전까지다")
	void payDayAnchor() {
		BudgetPeriod period = BudgetPeriod.of("202609", 25);

		assertThat(period.from()).isEqualTo(LocalDate.of(2026, 9, 25));
		assertThat(period.to()).isEqualTo(LocalDate.of(2026, 10, 25));
	}

	@Test
	@DisplayName("기준일 28은 모든 달에 존재해 연말·2월 경계에서도 성립한다")
	void maxAnchorAcrossYearAndFebruary() {
		BudgetPeriod december = BudgetPeriod.of("202612", 28);
		assertThat(december.to()).isEqualTo(LocalDate.of(2027, 1, 28));

		BudgetPeriod january = BudgetPeriod.of("202701", 28);
		assertThat(january.to()).isEqualTo(LocalDate.of(2027, 2, 28));
	}

	@Test
	@DisplayName("오늘이 기준일 이후면 이번 달, 이전이면 전월 라벨의 주기가 현재 주기다")
	void currentPeriod() {
		LocalDate today = LocalDate.of(2026, 9, 10);

		assertThat(BudgetPeriod.current(today, 1).month()).isEqualTo("202609");
		assertThat(BudgetPeriod.current(today, 25).month()).isEqualTo("202608");
		assertThat(BudgetPeriod.current(LocalDate.of(2026, 9, 25), 25).month()).isEqualTo("202609");
		assertThat(BudgetPeriod.current(LocalDate.of(2027, 1, 10), 25).month()).isEqualTo("202612");
	}

	@Test
	@DisplayName("윤년 2월에도 기준일이 밀리지 않는다")
	void leapYearFebruary() {
		BudgetPeriod leapFebruary = BudgetPeriod.of("202802", 28);

		assertThat(leapFebruary.from()).isEqualTo(LocalDate.of(2028, 2, 28));
		assertThat(leapFebruary.to()).isEqualTo(LocalDate.of(2028, 3, 28));

		BudgetPeriod acrossLeapDay = BudgetPeriod.of("202801", 28);
		assertThat(acrossLeapDay.to()).isEqualTo(LocalDate.of(2028, 2, 28));
	}
}
