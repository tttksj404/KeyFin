package com.finset.key_fin.payment.controller;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

import java.time.LocalDate;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse.Approval;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse.EstimatedDetail;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.CardSummary;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.Estimated;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.Statement;
import com.finset.key_fin.payment.entity.CardBilling.BillingStatus;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.service.CardBillingQueryService;

class CardBillingControllerTest {

	private CardBillingQueryService cardBillingQueryService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		cardBillingQueryService = mock(CardBillingQueryService.class);
		mockMvc = standaloneSetup(new CardBillingController(cardBillingQueryService))
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
	void returnsSummaryWithNullsForLegacyCard() throws Exception {
		when(cardBillingQueryService.summary(1L)).thenReturn(new CardBillingSummaryResponse(
				LocalDate.of(2026, 9, 16), LocalDate.of(2026, 9, 14), LocalDate.of(2026, 9, 21),
				List.of(
						new CardSummary(3L, "신한 테스트카드", 3, 5L,
								new Estimated(15000L, 2, LocalDate.of(2026, 9, 23)),
								new Statement(12L, LocalDate.of(2026, 9, 14), 80000L, BillingStatus.UNPAID, LocalDate.of(2026, 9, 16), null)),
						new CardSummary(4L, "KB 테스트카드", null, 5L, new Estimated(0L, 0, null), null))));

		mockMvc.perform(get("/api/v1/cards/billings"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.asOf").value("2026-09-16"))
				.andExpect(jsonPath("$.data.nextBillingDate").value("2026-09-21"))
				.andExpect(jsonPath("$.data.cards[0].estimated.amount").value(15000))
				.andExpect(jsonPath("$.data.cards[0].estimated.withdrawalDate").value("2026-09-23"))
				.andExpect(jsonPath("$.data.cards[0].latestStatement.status").value("UNPAID"))
				.andExpect(jsonPath("$.data.cards[1].withdrawalWeekday").value(nullValue()))
				.andExpect(jsonPath("$.data.cards[1].estimated.withdrawalDate").value(nullValue()))
				.andExpect(jsonPath("$.data.cards[1].latestStatement").value(nullValue()));
	}

	@Test
	void forwardsRangeAndReturnsDetail() throws Exception {
		when(cardBillingQueryService.detail(1L, 3L, "202607", "202609")).thenReturn(new CardBillingDetailResponse(
				LocalDate.of(2026, 9, 16), LocalDate.of(2026, 9, 14), LocalDate.of(2026, 9, 21),
				3L, "신한 테스트카드", 3, 5L,
				new EstimatedDetail(15000L, LocalDate.of(2026, 9, 23),
						List.of(new Approval(502L, LocalDate.of(2026, 9, 15), "GS25 역삼점", 6000L))),
				"202607", "202609", List.of()));

		mockMvc.perform(get("/api/v1/cards/3/billings").param("from", "202607").param("to", "202609"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.cardId").value(3))
				.andExpect(jsonPath("$.data.estimated.approvals[0].transactionId").value(502))
				.andExpect(jsonPath("$.data.estimated.approvals[0].merchantName").value("GS25 역삼점"))
				.andExpect(jsonPath("$.data.from").value("202607"))
				.andExpect(jsonPath("$.data.statements").isEmpty());
	}

	@Test
	void detailWithoutRangeUsesDefaults() throws Exception {
		when(cardBillingQueryService.detail(1L, 3L, null, null)).thenReturn(new CardBillingDetailResponse(
				LocalDate.of(2026, 9, 16), LocalDate.of(2026, 9, 14), LocalDate.of(2026, 9, 21),
				3L, "신한 테스트카드", 3, 5L, new EstimatedDetail(0L, LocalDate.of(2026, 9, 23), List.of()),
				"202608", "202609", List.of()));

		mockMvc.perform(get("/api/v1/cards/3/billings"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.from").value("202608"));
		verify(cardBillingQueryService).detail(1L, 3L, null, null);
	}

	@Test
	void mapsServiceErrors() throws Exception {
		doThrow(new BusinessException(PaymentErrorCode.CARD_NOT_FOUND)).when(cardBillingQueryService).detail(1L, 99L, null, null);
		doThrow(new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE)).when(cardBillingQueryService).detail(1L, 3L, "2026-09", null);

		mockMvc.perform(get("/api/v1/cards/99/billings"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("PAY_013"));
		mockMvc.perform(get("/api/v1/cards/3/billings").param("from", "2026-09"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}
}
