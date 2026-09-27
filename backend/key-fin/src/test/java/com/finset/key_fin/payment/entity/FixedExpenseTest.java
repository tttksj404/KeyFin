package com.finset.key_fin.payment.entity;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.YearMonth;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class FixedExpenseTest {

	@Test
	@DisplayName("출금일 31은 30일 달·2월(평년 28, 윤년 29)에서 말일로 보정되고 31일 달은 그대로")
	void paymentDateIsClampedToLastDayOfMonth() {
		FixedExpense expense = FixedExpense.register(null, "월세", ExpenseType.RENT, 550000, false, 31, 1L);

		assertThat(expense.paymentDateIn(YearMonth.of(2026, 4))).isEqualTo(LocalDate.of(2026, 4, 30));
		assertThat(expense.paymentDateIn(YearMonth.of(2026, 2))).isEqualTo(LocalDate.of(2026, 2, 28));
		assertThat(expense.paymentDateIn(YearMonth.of(2028, 2))).isEqualTo(LocalDate.of(2028, 2, 29));
		assertThat(expense.paymentDateIn(YearMonth.of(2026, 10))).isEqualTo(LocalDate.of(2026, 10, 31));
	}

	@Test
	@DisplayName("출금일 15는 어느 달이든 15일")
	void paymentDateWithinMonthIsUnchanged() {
		FixedExpense expense = FixedExpense.register(null, "구독", ExpenseType.SUBSCRIPTION, 7900, false, 15, 1L);

		assertThat(expense.paymentDateIn(YearMonth.of(2026, 2))).isEqualTo(LocalDate.of(2026, 2, 15));
	}

	@Test
	@DisplayName("수동 등록은 fin_subscription_id가 없어 동기화 항목이 아니고, 삭제는 비활성화로 표현된다")
	void manualExpenseLifecycle() {
		FixedExpense expense = FixedExpense.register(null, "월세", ExpenseType.RENT, 550000, false, 15, 1L);

		assertThat(expense.isSynced()).isFalse();
		assertThat(expense.isActive()).isTrue();

		expense.deactivate();

		assertThat(expense.isActive()).isFalse();
	}

	@Test
	@DisplayName("동기화 항목은 생성 시점에 fin_subscription_id를 갖고 출금 계좌는 없으며, syncFrom은 금액·결제일을 갱신하고 다시 활성화한다")
	void syncedExpenseLifecycle() {
		FixedExpense expense = FixedExpense.sync(null, "SUB20260913205959144", "FLO", 8900, 13);

		assertThat(expense.isSynced()).isTrue();
		assertThat(expense.getExpenseType()).isEqualTo(ExpenseType.SUBSCRIPTION);
		assertThat(expense.getWithdrawalAccountId()).isNull();
		assertThat(expense.isVariable()).isFalse();
		assertThat(expense.isActive()).isTrue();

		expense.deactivate();
		expense.syncFrom("FLO 개인", 9900, 15);

		assertThat(expense.getName()).isEqualTo("FLO 개인");
		assertThat(expense.getAmount()).isEqualTo(9900L);
		assertThat(expense.getPaymentDay()).isEqualTo(15);
		assertThat(expense.isActive()).isTrue();
		assertThat(expense.getFinSubscriptionId()).isEqualTo("SUB20260913205959144");
	}

	@Test
	@DisplayName("CARD_BILL만 수동 등록이 막힌다")
	void onlyCardBillIsBlockedForManualRegistration() {
		assertThat(ExpenseType.CARD_BILL.isManualAllowed()).isFalse();
		assertThat(ExpenseType.RENT.isManualAllowed()).isTrue();
		assertThat(ExpenseType.SUBSCRIPTION.isManualAllowed()).isTrue();
		assertThat(ExpenseType.UTILITY.isManualAllowed()).isTrue();
		assertThat(ExpenseType.LOAN.isManualAllowed()).isTrue();
	}
}
