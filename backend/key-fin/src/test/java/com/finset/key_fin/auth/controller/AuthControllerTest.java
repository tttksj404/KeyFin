package com.finset.key_fin.auth.controller;

import com.finset.key_fin.auth.dto.request.LoginRequest;
import com.finset.key_fin.auth.dto.request.RefreshTokenRequest;
import com.finset.key_fin.auth.dto.request.SignupRequest;
import com.finset.key_fin.auth.dto.response.AccessTokenResponse;
import com.finset.key_fin.auth.dto.response.LoginResponse;
import com.finset.key_fin.auth.dto.response.SignupResponse;
import com.finset.key_fin.auth.service.AuthService;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class AuthControllerTest {

	private AuthService authService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		authService = mock(AuthService.class);
		mockMvc = standaloneSetup(new AuthController(authService))
				.setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
				.build();
	}

	@Test
	void createsUserOnSignup() throws Exception {
		when(authService.signup(any(SignupRequest.class))).thenReturn(new SignupResponse(1L));

		mockMvc.perform(post("/api/v1/auth/signup")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"email":"qwer@qwer.com","password":"qwer1234@","name":"김예린"}
								"""))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.userId").value(1));
	}

	@Test
	void rejectsInvalidSignupInput() throws Exception {
		mockMvc.perform(post("/api/v1/auth/signup")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"email\":\"invalid-email\",\"password\":\"\",\"name\":\"\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@Test
	void returnsTokensAndUserOnLogin() throws Exception {
		when(authService.login(any(LoginRequest.class))).thenReturn(new LoginResponse(
				"access-token",
				"refresh-token",
				new LoginResponse.UserSummary(1L, "김예린")
		));

		mockMvc.perform(post("/api/v1/auth/login")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"email":"qwer@qwer.com","password":"qwer1234@"}
								"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.accessToken").value("access-token"))
				.andExpect(jsonPath("$.data.refreshToken").value("refresh-token"))
				.andExpect(jsonPath("$.data.user.id").value(1))
				.andExpect(jsonPath("$.data.user.name").value("김예린"));
	}

	@Test
	void returnsNewAccessTokenOnRefresh() throws Exception {
		when(authService.refresh(any(RefreshTokenRequest.class)))
				.thenReturn(new AccessTokenResponse("new-access-token"));

		mockMvc.perform(post("/api/v1/auth/refresh")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"refreshToken\":\"refresh-token\"}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.accessToken").value("new-access-token"));
	}

	@Test
	void logsOutAuthenticatedUser() throws Exception {
		UsernamePasswordAuthenticationToken authentication =
				UsernamePasswordAuthenticationToken.authenticated(1L, null, java.util.List.of());
		SecurityContextHolder.getContext().setAuthentication(authentication);

		try {
			mockMvc.perform(post("/api/v1/auth/logout"))
					.andExpect(status().isOk())
					.andExpect(jsonPath("$.success").value(true))
					.andExpect(jsonPath("$.data").doesNotExist());
		} finally {
			SecurityContextHolder.clearContext();
		}

		org.mockito.Mockito.verify(authService).logout(1L);
	}

	@Test
	void rejectsInvalidLoginInput() throws Exception {
		mockMvc.perform(post("/api/v1/auth/login")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"email\":\"invalid-email\",\"password\":\"\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@Test
	void rejectsBlankRefreshToken() throws Exception {
		mockMvc.perform(post("/api/v1/auth/refresh")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"refreshToken\":\"\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}
}
