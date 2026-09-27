package com.finset.key_fin.budget.controller;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
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
import org.springframework.http.MediaType;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest;
import com.finset.key_fin.budget.dto.response.BudgetConfirmResponse;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse;
import com.finset.key_fin.budget.dto.request.EmergencyFundRequest;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.Emergency;
import com.finset.key_fin.budget.dto.response.EmergencyFundResponse;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.EnvelopeBoard;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.Total;
import com.finset.key_fin.budget.dto.response.BudgetProposalResponse;
import com.finset.key_fin.budget.dto.response.BudgetProposalResponse.EnvelopeProposal;
import com.finset.key_fin.budget.service.BudgetService;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;

class BudgetControllerTest {

	private BudgetService budgetService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		budgetService = mock(BudgetService.class);
		mockMvc = standaloneSetup(new BudgetController(budgetService))
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
	void createsProposalForAuthenticatedUser() throws Exception {
		BudgetProposalResponse response = new BudgetProposalResponse(
				11L, "202609", "PROPOSED", "최근 3개월 평균 (2026-06-02~2026-09-01)",
				List.of(new EnvelopeProposal(1, "외식", 121000, 120652)));
		when(budgetService.propose(1L)).thenReturn(response);

		mockMvc.perform(post("/api/v1/budgets/proposals"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.budgetId").value(11))
				.andExpect(jsonPath("$.data.month").value("202609"))
				.andExpect(jsonPath("$.data.status").value("PROPOSED"))
				.andExpect(jsonPath("$.data.envelopes[0].envelopeId").value(1))
				.andExpect(jsonPath("$.data.envelopes[0].proposedAmount").value(121000));
	}

	@Test
	void returnsCurrentBudgetForAuthenticatedUser() throws Exception {
		when(budgetService.getCurrent(1L)).thenReturn(new BudgetCurrentResponse(
				11L, "202609", LocalDate.of(2026, 9, 1), LocalDate.of(2026, 9, 30), "CONFIRMED",
				new Total(780000, 298000, 482000, 61),
				List.of(EnvelopeBoard.confirmed(3, "의료·건강", 0, 30000, -30000, null)),
				Emergency.of(0, 0)));

		mockMvc.perform(get("/api/v1/budgets/current"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.status").value("CONFIRMED"))
				.andExpect(jsonPath("$.data.periodTo").value("2026-09-30"))
				.andExpect(jsonPath("$.data.total.remainingRate").value(61))
				.andExpect(jsonPath("$.data.envelopes[0].remaining").value(-30000))
				.andExpect(jsonPath("$.data.envelopes[0].remainingRate").value((Object) null));
	}

	@Test
	void updatesEmergencyFund() throws Exception {
		when(budgetService.updateEmergency(eq(1L), eq(11L), any(EmergencyFundRequest.class)))
				.thenReturn(new EmergencyFundResponse(11L, Emergency.of(200000, 45000)));

		mockMvc.perform(put("/api/v1/budgets/11/emergency")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"amount\":200000}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.budgetId").value(11))
				.andExpect(jsonPath("$.data.emergency.amount").value(200000))
				.andExpect(jsonPath("$.data.emergency.remaining").value(155000));
	}

	@Test
	void rejectsNegativeOrMissingEmergencyAmount() throws Exception {
		mockMvc.perform(put("/api/v1/budgets/11/emergency")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"amount\":-1000}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
		mockMvc.perform(put("/api/v1/budgets/11/emergency")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{}"))
				.andExpect(status().isBadRequest());
	}

	@Test
	void confirmsBudgetForAuthenticatedUser() throws Exception {
		when(budgetService.confirm(eq(1L), eq(11L), any(BudgetConfirmRequest.class)))
				.thenReturn(new BudgetConfirmResponse(11L, "202609", "CONFIRMED"));

		mockMvc.perform(put("/api/v1/budgets/11/confirm")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"envelopes\":[{\"envelopeId\":1,\"amount\":280000}]}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.budgetId").value(11))
				.andExpect(jsonPath("$.data.status").value("CONFIRMED"));
	}

	@Test
	void rejectsConfirmWithoutEnvelopes() throws Exception {
		mockMvc.perform(put("/api/v1/budgets/11/confirm")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"envelopes\":[]}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}
}
