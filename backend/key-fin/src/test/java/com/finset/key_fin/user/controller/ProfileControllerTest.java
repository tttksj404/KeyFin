package com.finset.key_fin.user.controller;

import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.user.dto.request.ProfileUpdateRequest;
import com.finset.key_fin.user.dto.response.ProfileResponse;
import com.finset.key_fin.user.entity.EmploymentStatus;
import com.finset.key_fin.user.service.ProfileService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class ProfileControllerTest {

	private static final long USER_ID = 1L;

	private ProfileService profileService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		profileService = mock(ProfileService.class);
		mockMvc = standaloneSetup(new ProfileController(profileService))
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
	void 프로필을_입력한다() throws Exception {
		when(profileService.updateProfile(eq(USER_ID), any(ProfileUpdateRequest.class)))
				.thenReturn(new ProfileResponse(
						LocalDate.of(2001, 3, 14), "11680", EmploymentStatus.EMPLOYED, "2400_3600"));

		mockMvc.perform(put("/api/v1/profile")
						.contentType("application/json")
						.content("""
								{"birthDate":"2001-03-14","regionCode":"11680","employmentStatus":"EMPLOYED","incomeBand":"2400_3600"}
								"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.birthDate").value("2001-03-14"))
				.andExpect(jsonPath("$.data.regionCode").value("11680"))
				.andExpect(jsonPath("$.data.employmentStatus").value("EMPLOYED"))
				.andExpect(jsonPath("$.data.incomeBand").value("2400_3600"));

		verify(profileService).updateProfile(eq(USER_ID), any(ProfileUpdateRequest.class));
	}

	@Test
	void 잘못된_지역_코드는_거절한다() throws Exception {
		mockMvc.perform(put("/api/v1/profile")
						.contentType("application/json")
						.content("{\"regionCode\":\"SEOUL\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}
}
