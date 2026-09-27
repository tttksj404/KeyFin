package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.YearMonth;

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
@Sql(scripts = "/sql/subscription-sync-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class PaymentCalendarServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;

	@Autowired
	private PaymentCalendarService paymentCalendarService;

	@Test
	@DisplayName("저장된 활성 항목을 날짜별로 묶는다 — 수동은 FIXED, 동기화는 CARD_SUBSCRIPTION, 비활성 제외, 31일은 말일 보정")
	void buildsCalendarForMonth() {
		PaymentCalendarResponse response = paymentCalendarService.getCalendar(USER, YearMonth.of(2026, 9));

		assertThat(response.month()).isEqualTo("202609");
		assertThat(response.days()).extracting(Day::date).containsExactly(
				LocalDate.of(2026, 9, 5), LocalDate.of(2026, 9, 13), LocalDate.of(2026, 9, 15), LocalDate.of(2026, 9, 30));

		Day fifteenth = response.days().get(2);
		assertThat(fifteenth.items()).extracting(Item::name).containsExactly("월세");
		assertThat(fifteenth.items().get(0).type()).isEqualTo(CalendarItemType.FIXED);
		assertThat(fifteenth.items().get(0).withdrawalAccountId()).isEqualTo(9504L);
		assertThat(fifteenth.items().get(0).prepared()).isFalse();
		assertThat(fifteenth.items().get(0).shortage()).isEqualTo(50000L);
		Item flo = response.days().get(1).items().get(0);
		assertThat(flo.type()).isEqualTo(CalendarItemType.CARD_SUBSCRIPTION);
		assertThat(flo.withdrawalAccountId()).isNull();

		Item telecom = response.days().get(3).items().get(0);
		assertThat(telecom.name()).isEqualTo("통신비");
		assertThat(telecom.estimated()).isTrue();

		assertThat(response.days()).flatExtracting(Day::items).extracting(Item::name)
				.doesNotContain("헬스장", "멜론");
	}

	@Test
	@DisplayName("항목이 없는 달은 빈 days")
	void emptyMonthWhenNothingActive() {

		PaymentCalendarResponse response = paymentCalendarService.getCalendar(985L, YearMonth.of(2026, 9));

		assertThat(response.days()).isEmpty();
	}
}
