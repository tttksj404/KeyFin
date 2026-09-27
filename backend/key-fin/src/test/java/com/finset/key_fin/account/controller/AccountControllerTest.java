package com.finset.key_fin.account.controller;

import com.finset.key_fin.account.dto.response.AccountListResponse;
import com.finset.key_fin.account.dto.response.AccountListResponse.AccountItem;
import com.finset.key_fin.account.exception.AccountErrorCode;
import com.finset.key_fin.account.service.AccountService;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class AccountControllerTest {

	private static final long USER_ID = 1L;

	private AccountService accountService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		accountService = mock(AccountService.class);
		mockMvc = standaloneSetup(new AccountController(accountService))
				.setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
				.build();
		SecurityContextHolder.getContext().setAuthentication(
				UsernamePasswordAuthenticationToken.authenticated(USER_ID, null, List.of())
		);
	}

	@AfterEach
	void tearDown() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void 연결_계좌_목록과_잔액_업데이트_시각을_반환한다() throws Exception {
		LocalDateTime updatedAt = LocalDateTime.of(2026, 9, 11, 14, 30);
		when(accountService.getManagedAccounts(USER_ID)).thenReturn(new AccountListResponse(List.of(
				new AccountItem(3L, "0010011073486799", "한국은행", "생활비", true, true, 1_500_000L, updatedAt)
		)));

		mockMvc.perform(get("/api/v1/accounts"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.items[0].id").value(3))
				.andExpect(jsonPath("$.data.items[0].isIncome").value(true))
				.andExpect(jsonPath("$.data.items[0].isManaged").value(true))
				.andExpect(jsonPath("$.data.items[0].balance").value(1_500_000))
				.andExpect(jsonPath("$.data.items[0].balanceUpdatedAt").value("2026-09-11T14:30:00"));

		verify(accountService).getManagedAccounts(USER_ID);
	}

	@Test
	void 활성_사용자가_없으면_404를_반환한다() throws Exception {
		when(accountService.getManagedAccounts(USER_ID))
				.thenThrow(new BusinessException(UserErrorCode.USER_NOT_FOUND));

		mockMvc.perform(get("/api/v1/accounts"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("USER_001"));
	}

	@Test
	void 수입_계좌를_지정한다() throws Exception {
		mockMvc.perform(put("/api/v1/accounts/3/income"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data").doesNotExist());

		verify(accountService).designateIncomeAccount(USER_ID, 3L);
	}

	@Test
	void 본인_소유_계좌가_아니면_404를_반환한다() throws Exception {
		doThrow(new BusinessException(AccountErrorCode.ACCOUNT_NOT_FOUND))
				.when(accountService).designateIncomeAccount(USER_ID, 99L);

		mockMvc.perform(put("/api/v1/accounts/99/income"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("ACCOUNT_001"));
	}
}
