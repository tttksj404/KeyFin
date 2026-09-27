package com.finset.key_fin.user.controller;

import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.user.dto.request.CoachPersonaUpdateRequest;
import com.finset.key_fin.user.dto.request.NotificationSettingsUpdateRequest;
import com.finset.key_fin.user.dto.request.TransferSettingsUpdateRequest;
import com.finset.key_fin.user.dto.response.CoachPersonaResponse;
import com.finset.key_fin.user.dto.response.NotificationSettingsResponse;
import com.finset.key_fin.user.dto.response.TransferSettingsResponse;
import com.finset.key_fin.user.entity.CoachPersona;
import com.finset.key_fin.user.service.UserSettingsService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import com.finset.key_fin.user.dto.request.BudgetSettingsUpdateRequest;
import com.finset.key_fin.user.dto.response.BudgetSettingsResponse;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.time.LocalTime;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class UserSettingsControllerTest {

	private static final long USER_ID = 1L;

	private UserSettingsService userSettingsService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		userSettingsService = mock(UserSettingsService.class);
		mockMvc = standaloneSetup(new UserSettingsController(userSettingsService))
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
	void 예산_기준일을_조회한다() throws Exception {
		when(userSettingsService.getBudgetSettings(USER_ID)).thenReturn(new BudgetSettingsResponse(25));

		mockMvc.perform(get("/api/v1/settings/budget"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.budgetAnchorDay").value(25));
	}

	@Test
	void 예산_기준일을_변경한다() throws Exception {
		when(userSettingsService.updateBudgetSettings(eq(USER_ID), any(BudgetSettingsUpdateRequest.class)))
				.thenReturn(new BudgetSettingsResponse(25));

		mockMvc.perform(put("/api/v1/settings/budget")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"budgetAnchorDay\":25}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.budgetAnchorDay").value(25));
	}

	@Test
	void 범위_밖_예산_기준일은_400을_반환한다() throws Exception {
		for (String body : new String[]{"{\"budgetAnchorDay\":0}", "{\"budgetAnchorDay\":29}", "{}"}) {
			mockMvc.perform(put("/api/v1/settings/budget")
							.contentType(MediaType.APPLICATION_JSON)
							.content(body))
					.andExpect(status().isBadRequest())
					.andExpect(jsonPath("$.code").value("COMMON_001"));
		}

		verifyNoInteractions(userSettingsService);
	}

	@Test
	void 이체_설정을_조회한다() throws Exception {
		when(userSettingsService.getTransferSettings(USER_ID))
				.thenReturn(new TransferSettingsResponse(true, 1_000_000L, 2_000_000L));

		mockMvc.perform(get("/api/v1/settings/transfer"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.transferConsent").value(true))
				.andExpect(jsonPath("$.data.transferLimitOnce").value(1_000_000));

		verify(userSettingsService).getTransferSettings(USER_ID);
	}

	@Test
	void 알림_설정을_조회한다() throws Exception {
		when(userSettingsService.getNotificationSettings(USER_ID))
				.thenReturn(new NotificationSettingsResponse(
						true, false, true, false, LocalTime.of(23, 0), LocalTime.of(8, 0)));

		mockMvc.perform(get("/api/v1/settings/notifications"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.notiCoaching").value(true))
				.andExpect(jsonPath("$.data.notiBudgetAlert").value(false))
				.andExpect(jsonPath("$.data.notiTransfer").value(true))
				.andExpect(jsonPath("$.data.notiCleanup").value(false))
				.andExpect(jsonPath("$.data.quietHoursStart").value("23:00:00"))
				.andExpect(jsonPath("$.data.quietHoursEnd").value("08:00:00"));

		verify(userSettingsService).getNotificationSettings(USER_ID);
	}

	@Test
	void 코치_말투를_조회한다() throws Exception {
		when(userSettingsService.getCoachPersona(USER_ID))
				.thenReturn(new CoachPersonaResponse(CoachPersona.DODO));

		mockMvc.perform(get("/api/v1/settings/coach"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.coachPersona").value("DODO"));

		verify(userSettingsService).getCoachPersona(USER_ID);
	}

	@Test
	void 이체_설정을_변경한다() throws Exception {
		when(userSettingsService.updateTransferSettings(
				eq(USER_ID), any(TransferSettingsUpdateRequest.class)))
				.thenReturn(new TransferSettingsResponse(true, 1_000_000L, 2_000_000L));

		mockMvc.perform(put("/api/v1/settings/transfer")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"transferConsent":true,"transferLimitOnce":1000000,"transferLimitDaily":2000000}
								"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.transferConsent").value(true));
	}

	@Test
	void 알림_설정을_변경한다() throws Exception {
		mockMvc.perform(put("/api/v1/settings/notifications")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"notiCoaching":true,"notiBudgetAlert":true,"notiTransfer":true,"notiCleanup":false,"quietHoursStart":"23:00","quietHoursEnd":"08:00"}
								"""))
				.andExpect(status().isOk())
				.andExpect(content().string(""));

		verify(userSettingsService).updateNotificationSettings(
				eq(USER_ID), any(NotificationSettingsUpdateRequest.class));
	}

	@Test
	void 코치_말투를_변경한다() throws Exception {
		mockMvc.perform(put("/api/v1/settings/coach")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"coachPersona\":\"DODO\"}"))
				.andExpect(status().isOk())
				.andExpect(content().string(""));

		verify(userSettingsService).updateCoachPersona(
				eq(USER_ID), any(CoachPersonaUpdateRequest.class));
	}

	@Test
	void 필수_알림_설정이_누락되면_400을_반환한다() throws Exception {
		mockMvc.perform(put("/api/v1/settings/notifications")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"notiBudgetAlert":true,"notiTransfer":true,"notiCleanup":false}
								"""))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@Test
	void 지원하지_않는_코치_말투는_400을_반환한다() throws Exception {
		mockMvc.perform(put("/api/v1/settings/coach")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"coachPersona\":\"UNKNOWN\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_002"));

		verifyNoInteractions(userSettingsService);
	}
}
