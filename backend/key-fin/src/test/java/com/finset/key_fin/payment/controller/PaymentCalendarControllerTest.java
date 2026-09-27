package com.finset.key_fin.payment.controller;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.List;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.CalendarItemType;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Day;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Item;
import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.service.PaymentCalendarService;

class PaymentCalendarControllerTest {

	private PaymentCalendarService paymentCalendarService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		paymentCalendarService = mock(PaymentCalendarService.class);
		Clock clock = Clock.fixed(Instant.parse("2026-09-10T03:00:00Z"), ZoneId.of("Asia/Seoul"));
		mockMvc = standaloneSetup(new PaymentCalendarController(paymentCalendarService, clock))
				.setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
				.build();
		SecurityContextHolder.getContext().setAuthentication(
				UsernamePasswordAuthenticationToken.authenticated(1L, null, List.of()));
	}

	@AfterEach
	void tearDown() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void returnsCalendarForRequestedMonth() throws Exception {
		when(paymentCalendarService.getCalendar(1L, YearMonth.of(2026, 10))).thenReturn(new PaymentCalendarResponse(
				"202610",
				List.of(new Day(LocalDate.of(2026, 10, 15), List.of(
						new Item(CalendarItemType.FIXED, 7L, null, "월세", ExpenseType.RENT, 550000, false, 3L, null, null),
						new Item(CalendarItemType.CARD_SUBSCRIPTION, 8L, null, "FLO", ExpenseType.SUBSCRIPTION, 8900, false, null, null, null))))));

		mockMvc.perform(get("/api/v1/payments/calendar").param("month", "202610"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.month").value("202610"))
				.andExpect(jsonPath("$.data.days[0].date").value("2026-10-15"))
				.andExpect(jsonPath("$.data.days[0].items[0].type").value("FIXED"))
				.andExpect(jsonPath("$.data.days[0].items[1].type").value("CARD_SUBSCRIPTION"))
				.andExpect(jsonPath("$.data.days[0].items[1].withdrawalAccountId").value((Object) null))
				.andExpect(jsonPath("$.data.days[0].items[0].prepared").value((Object) null));
	}

	@Test
	void defaultsToCurrentMonthWhenMonthOmitted() throws Exception {
		when(paymentCalendarService.getCalendar(1L, YearMonth.of(2026, 9)))
				.thenReturn(new PaymentCalendarResponse("202609", List.of()));

		mockMvc.perform(get("/api/v1/payments/calendar"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.month").value("202609"))
				.andExpect(jsonPath("$.data.days").isEmpty());
	}

	@Test
	void rejectsMalformedMonth() throws Exception {
		mockMvc.perform(get("/api/v1/payments/calendar").param("month", "202613"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}
}
