package com.finset.key_fin.fincoin.controller;

import com.finset.key_fin.auth.config.SecurityConfig;
import com.finset.key_fin.auth.exception.AuthErrorCode;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.auth.jwt.TokenType;
import com.finset.key_fin.auth.security.JwtAccessDeniedHandler;
import com.finset.key_fin.auth.security.JwtAuthenticationEntryPoint;
import com.finset.key_fin.auth.security.JwtAuthenticationFilter;
import com.finset.key_fin.auth.security.SecurityErrorResponseWriter;
import com.finset.key_fin.fincoin.dto.response.FinCoinBalanceResponse;
import com.finset.key_fin.fincoin.dto.response.FinCoinResponse;
import com.finset.key_fin.fincoin.dto.response.FinCoinResponse.FinCoinHistoryResponse;
import com.finset.key_fin.fincoin.entity.FinCoinReason;
import com.finset.key_fin.fincoin.service.FinCoinService;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.time.LocalDate;
import java.util.List;

import static org.hamcrest.Matchers.aMapWithSize;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(FinCoinController.class)
@Import({SecurityConfig.class, JwtAuthenticationFilter.class, JwtAuthenticationEntryPoint.class,
		JwtAccessDeniedHandler.class, SecurityErrorResponseWriter.class})
class FinCoinControllerTest {

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private FinCoinService finCoinService;

	@MockitoBean
	private JwtTokenProvider jwtTokenProvider;

	@Test
	void returnsFinCoinsWithDefaultPageSizeForTokenOwner() throws Exception {
		when(finCoinService.getFinCoins(981L, null, 20)).thenReturn(new FinCoinResponse(
				List.of(new FinCoinHistoryResponse(
						8_100_000_009L, -150, 700, FinCoinReason.PURCHASE, "아이템 구매", LocalDate.of(2026, 9, 2)
				)), null
		));

		mockMvc.perform(authenticatedRequest().param("userId", "982"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.code").value("SUCCESS"))
				.andExpect(jsonPath("$.data").value(aMapWithSize(2)))
				.andExpect(jsonPath("$.data.balance").doesNotHaveJsonPath())
				.andExpect(jsonPath("$.data.items[0].id").value(8_100_000_009L))
				.andExpect(jsonPath("$.data.items[0].delta").value(-150))
				.andExpect(jsonPath("$.data.items[0].balanceAfter").value(700))
				.andExpect(jsonPath("$.data.items[0].reasonCode").value("PURCHASE"))
				.andExpect(jsonPath("$.data.items[0].reasonText").value("아이템 구매"))
				.andExpect(jsonPath("$.data.items[0].grantDate").value("2026-09-02"))
				.andExpect(jsonPath("$.data.nextCursor").hasJsonPath())
				.andExpect(jsonPath("$.data.nextCursor").value(nullValue()));

		verify(finCoinService).getFinCoins(981L, null, 20);
	}

	@Test
	void bindsCursorAndReturnsNextCursor() throws Exception {
		when(finCoinService.getFinCoins(981L, 8_100_000_009L, 1)).thenReturn(new FinCoinResponse(
				List.of(new FinCoinHistoryResponse(
						8_100_000_007L, 500, 850, FinCoinReason.MONTHLY, "월간 보상", LocalDate.of(2026, 9, 4)
				)), 8_100_000_007L
		));

		mockMvc.perform(authenticatedRequest().param("cursor", "8100000009").param("size", "1"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.nextCursor").value(8_100_000_007L));

		verify(finCoinService).getFinCoins(981L, 8_100_000_009L, 1);
	}

	@ParameterizedTest
	@ValueSource(ints = {1, 100})
	void acceptsPageSizeBoundaries(int size) throws Exception {
		when(finCoinService.getFinCoins(981L, null, size)).thenReturn(new FinCoinResponse(List.of(), null));

		mockMvc.perform(authenticatedRequest().param("size", Integer.toString(size)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data").value(aMapWithSize(2)))
				.andExpect(jsonPath("$.data.balance").doesNotHaveJsonPath())
				.andExpect(jsonPath("$.data.items").isEmpty())
				.andExpect(jsonPath("$.data.nextCursor").hasJsonPath())
				.andExpect(jsonPath("$.data.nextCursor").value(nullValue()));

		verify(finCoinService).getFinCoins(981L, null, size);
	}

	@ParameterizedTest
	@ValueSource(longs = {1, Long.MAX_VALUE})
	void acceptsPositiveLongCursorBoundaries(long cursor) throws Exception {
		when(finCoinService.getFinCoins(981L, cursor, 20)).thenReturn(new FinCoinResponse(List.of(), null));

		mockMvc.perform(authenticatedRequest().param("cursor", Long.toString(cursor)))
				.andExpect(status().isOk());

		verify(finCoinService).getFinCoins(981L, cursor, 20);
	}

	@ParameterizedTest
	@CsvSource({
			"size, 0", "size, -1", "size, 101", "size, 2147483647", "size, 2147483648",
			"size, abc", "size, 1.5", "cursor, 0", "cursor, -1", "cursor, abc",
			"cursor, 1.5", "cursor, 9223372036854775808"
	})
	void rejectsInvalidQueryWithCommonError(String parameter, String value) throws Exception {
		mockMvc.perform(authenticatedRequest().param(parameter, value))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_001"));

		verifyNoInteractions(finCoinService);
	}

	@Test
	void returnsExistingUserNotFoundError() throws Exception {
		when(finCoinService.getFinCoins(981L, null, 20))
				.thenThrow(new BusinessException(UserErrorCode.USER_NOT_FOUND));

		mockMvc.perform(authenticatedRequest())
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("USER_001"));
	}

	@ParameterizedTest
	@ValueSource(strings = {"/api/v1/fin-coins", "/api/v1/fin-coins/balance"})
	void rejectsRequestWithoutToken(String path) throws Exception {
		mockMvc.perform(get(path))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTH_005"));

		verifyNoInteractions(finCoinService);
	}

	@ParameterizedTest
	@EnumSource(value = AuthErrorCode.class, names = {"INVALID_TOKEN", "EXPIRED_TOKEN"})
	void preservesTokenErrors(AuthErrorCode errorCode) throws Exception {
		when(jwtTokenProvider.getUserId("bad-token", TokenType.ACCESS))
				.thenThrow(new BusinessException(errorCode));

		mockMvc.perform(get("/api/v1/fin-coins").header("Authorization", "Bearer bad-token"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value(errorCode.getCode()));

		verifyNoInteractions(finCoinService);
	}

	@ParameterizedTest
	@ValueSource(ints = {0, 700, Integer.MAX_VALUE})
	void returnsOnlyBalanceForAuthenticatedUser(int balance) throws Exception {
		when(finCoinService.getFinCoinBalance(981L)).thenReturn(new FinCoinBalanceResponse(balance));

		mockMvc.perform(authenticatedRequest("/api/v1/fin-coins/balance").param("userId", "982"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.code").value("SUCCESS"))
				.andExpect(jsonPath("$.data").value(aMapWithSize(1)))
				.andExpect(jsonPath("$.data.balance").value(balance));

		verify(finCoinService).getFinCoinBalance(981L);
	}

	@Test
	void returnsUserNotFoundForBalanceRequest() throws Exception {
		when(finCoinService.getFinCoinBalance(981L))
				.thenThrow(new BusinessException(UserErrorCode.USER_NOT_FOUND));

		mockMvc.perform(authenticatedRequest("/api/v1/fin-coins/balance"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("USER_001"));
	}

	@ParameterizedTest
	@EnumSource(value = AuthErrorCode.class, names = {"INVALID_TOKEN", "EXPIRED_TOKEN"})
	void preservesTokenErrorsForBalanceRequest(AuthErrorCode errorCode) throws Exception {
		when(jwtTokenProvider.getUserId("bad-token", TokenType.ACCESS))
				.thenThrow(new BusinessException(errorCode));

		mockMvc.perform(get("/api/v1/fin-coins/balance").header("Authorization", "Bearer bad-token"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value(errorCode.getCode()));

		verifyNoInteractions(finCoinService);
	}

	private MockHttpServletRequestBuilder authenticatedRequest() {
		return authenticatedRequest("/api/v1/fin-coins");
	}

	private MockHttpServletRequestBuilder authenticatedRequest(String path) {
		when(jwtTokenProvider.getUserId("coin-access-token", TokenType.ACCESS)).thenReturn(981L);
		return get(path).header("Authorization", "Bearer coin-access-token");
	}
}
