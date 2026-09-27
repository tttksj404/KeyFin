package com.finset.key_fin.user.controller;

import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.user.dto.request.AccountDeletionRequest;
import com.finset.key_fin.user.service.UserService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class UserControllerTest {

	private static final long USER_ID = 1L;

	private UserService userService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		userService = mock(UserService.class);
		mockMvc = standaloneSetup(new UserController(userService))
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
	void 회원을_탈퇴한다() throws Exception {
		mockMvc.perform(delete("/api/v1/users/me")
						.contentType("application/json")
						.content("{\"password\":\"qwer1234@\"}"))
				.andExpect(status().isNoContent());

		verify(userService).deleteAccount(eq(USER_ID), any(AccountDeletionRequest.class));
	}

	@Test
	void 현재_비밀번호가_누락되면_거절한다() throws Exception {
		mockMvc.perform(delete("/api/v1/users/me")
						.contentType("application/json")
						.content("{\"password\":\"\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}
}
