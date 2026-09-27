package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.CalendarItemType;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Day;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Item;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql(scripts = "/sql/card-billing-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class PaymentCalendarCardBillTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;

	@Autowired
	private PaymentCalendarService paymentCalendarService;

	@Test
	@DisplayName("카드 청구 합류 + 잔액 판정 — 결제완료는 납입일에 true/0, 과거 미결제는 null, 예정액은 이번 주 LIVE 승인 합계로 다음 출금일에, 같은 계좌는 날짜순 차감")
	void judgesCardBillsAndFixedExpenses() {
		PaymentCalendarResponse response = paymentCalendarService.getCalendar(USER, YearMonth.of(2026, 9));

		assertThat(response.days()).extracting(Day::date).containsExactly(
				LocalDate.of(2026, 9, 2), LocalDate.of(2026, 9, 9), LocalDate.of(2026, 9, 13),
				LocalDate.of(2026, 9, 15), LocalDate.of(2026, 9, 16), LocalDate.of(2026, 9, 20));

		Item paid = only(response, 0);
		assertThat(paid.type()).isEqualTo(CalendarItemType.CARD_BILL);
		assertThat(paid.cardId()).isEqualTo(9603L);
		assertThat(paid.name()).isEqualTo("신한 테스트카드");
		assertThat(paid.amount()).isEqualTo(30000L);
		assertThat(paid.estimated()).isFalse();
		assertThat(paid.prepared()).isTrue();
		assertThat(paid.shortage()).isZero();

		Item pastUnpaid = only(response, 1);
		assertThat(pastUnpaid.amount()).isEqualTo(80000L);
		assertThat(pastUnpaid.prepared()).isNull();
		assertThat(pastUnpaid.shortage()).isNull();

		Item flo = only(response, 2);
		assertThat(flo.type()).isEqualTo(CalendarItemType.CARD_SUBSCRIPTION);
		assertThat(flo.prepared()).isNull();

		Item rent = only(response, 3);
		assertThat(rent.amount()).isEqualTo(490000L);
		assertThat(rent.prepared()).isTrue();
		assertThat(rent.shortage()).isZero();

		Item estimated = only(response, 4);
		assertThat(estimated.type()).isEqualTo(CalendarItemType.CARD_BILL);
		assertThat(estimated.amount()).isEqualTo(15000L);
		assertThat(estimated.estimated()).isTrue();
		assertThat(estimated.withdrawalAccountId()).isEqualTo(9504L);
		assertThat(estimated.prepared()).isFalse();
		assertThat(estimated.shortage()).isEqualTo(5000L);

		Item telecom = only(response, 5);
		assertThat(telecom.withdrawalAccountId()).isEqualTo(9505L);
		assertThat(telecom.prepared()).isTrue();
		assertThat(telecom.shortage()).isZero();
	}

	@Test
	@DisplayName("다음 달에는 카드 청구 항목이 없고(예정액은 이번 주 것만) 고정지출은 판정 대상")
	void nextMonthHasNoCardBills() {
		PaymentCalendarResponse response = paymentCalendarService.getCalendar(USER, YearMonth.of(2026, 10));

		List<Item> items = response.days().stream().flatMap(day -> day.items().stream()).toList();
		assertThat(items).extracting(Item::type)
				.containsOnly(CalendarItemType.FIXED, CalendarItemType.CARD_SUBSCRIPTION);
		assertThat(items).filteredOn(item -> "월세".equals(item.name()))
				.singleElement().extracting(Item::prepared).isEqualTo(Boolean.TRUE);
	}

	private static Item only(PaymentCalendarResponse response, int dayIndex) {
		List<Item> items = response.days().get(dayIndex).items();
		assertThat(items).hasSize(1);
		return items.get(0);
	}
}
