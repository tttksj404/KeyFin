package com.finset.key_fin.payment.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

import java.util.List;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.payment.dto.request.FixedExpenseRequest;
import com.finset.key_fin.payment.dto.response.FixedExpenseIdResponse;
import com.finset.key_fin.payment.dto.response.FixedExpenseResponse;
import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.service.FixedExpenseService;

class FixedExpenseControllerTest {

	private static final String RENT_JSON =
			"{\"name\":\"월세\",\"expenseType\":\"RENT\",\"amount\":550000,\"isVariable\":false,\"paymentDay\":15,\"withdrawalAccountId\":3}";

	private FixedExpenseService fixedExpenseService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		fixedExpenseService = mock(FixedExpenseService.class);
		mockMvc = standaloneSetup(new FixedExpenseController(fixedExpenseService))
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
	void registersFixedExpenseWithCreated() throws Exception {
		when(fixedExpenseService.register(eq(1L), any(FixedExpenseRequest.class)))
				.thenReturn(new FixedExpenseIdResponse(7L));

		mockMvc.perform(post("/api/v1/fixed-expenses")
						.contentType(MediaType.APPLICATION_JSON)
						.content(RENT_JSON))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.id").value(7));
	}

	@Test
	void rejectsPaymentDayOutOfRange() throws Exception {
		mockMvc.perform(post("/api/v1/fixed-expenses")
						.contentType(MediaType.APPLICATION_JSON)
						.content(RENT_JSON.replace("\"paymentDay\":15", "\"paymentDay\":32")))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@Test
	void listsFixedExpenses() throws Exception {
		when(fixedExpenseService.list(1L)).thenReturn(List.of(
				new FixedExpenseResponse(7L, "월세", ExpenseType.RENT, 550000L, false, 15, 3L, false, null),
				new FixedExpenseResponse(8L, "FLO 개인", ExpenseType.SUBSCRIPTION, 7900L, false, 15, 3L, true, 2L)));

		mockMvc.perform(get("/api/v1/fixed-expenses"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.length()").value(2))
				.andExpect(jsonPath("$.data[0].isVariable").value(false))
				.andExpect(jsonPath("$.data[1].synced").value(true));
	}

	@Test
	void updatesFixedExpense() throws Exception {
		when(fixedExpenseService.update(eq(1L), eq(7L), any(FixedExpenseRequest.class)))
				.thenReturn(new FixedExpenseIdResponse(7L));

		mockMvc.perform(put("/api/v1/fixed-expenses/7")
						.contentType(MediaType.APPLICATION_JSON)
						.content(RENT_JSON))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.id").value(7));
	}

	@Test
	void assignsCardToSubscription() throws Exception {
		when(fixedExpenseService.assignCard(1L, 8L, 2L)).thenReturn(new FixedExpenseIdResponse(8L));

		mockMvc.perform(patch("/api/v1/fixed-expenses/8/card")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"cardId\":2}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.id").value(8));
	}

	@Test
	void rejectsCardAssignmentWithoutCardId() throws Exception {
		mockMvc.perform(patch("/api/v1/fixed-expenses/8/card")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{}"))
				.andExpect(status().isBadRequest());
	}

	@Test
	void deletesFixedExpense() throws Exception {
		mockMvc.perform(delete("/api/v1/fixed-expenses/7"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true));

		verify(fixedExpenseService).delete(1L, 7L);
	}
}
