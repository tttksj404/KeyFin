package com.finset.key_fin.auth.security;

import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Import(SecurityIntegrationTest.TestController.class)
class SecurityIntegrationTest extends SpringIntegrationTestSupport {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtTokenProvider jwtTokenProvider;

	@Test
	void rejectsProtectedRequestWithoutToken() throws Exception {
		mockMvc.perform(get("/test/security/authenticated"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("AUTH_005"))
				.andExpect(jsonPath("$.message").value("인증이 필요합니다."));
	}

	@Test
	void authenticatesProtectedRequestWithAccessToken() throws Exception {
		String accessToken = jwtTokenProvider.generateAccessToken(1L);

		mockMvc.perform(get("/test/security/authenticated")
						.header("Authorization", "Bearer " + accessToken))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data").value(1));
	}

	@Test
	void rejectsRefreshTokenAsAccessToken() throws Exception {
		String refreshToken = jwtTokenProvider.generateRefreshToken(1L);

		mockMvc.perform(get("/test/security/authenticated")
						.header("Authorization", "Bearer " + refreshToken))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTH_002"));
	}

	@Test
	void rejectsRequestWithoutRequiredAuthority() throws Exception {
		String accessToken = jwtTokenProvider.generateAccessToken(1L);

		mockMvc.perform(get("/test/security/admin")
						.header("Authorization", "Bearer " + accessToken))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("AUTH_006"))
				.andExpect(jsonPath("$.message").value("접근 권한이 없습니다."));
	}

	@RestController
	static class TestController {

		@GetMapping("/test/security/authenticated")
		BaseResponse<Long> authenticated(@AuthenticationPrincipal Long userId) {
			return BaseResponse.ok(userId);
		}

		@PreAuthorize("hasRole('ADMIN')")
		@GetMapping("/test/security/admin")
		BaseResponse<Void> admin() {
			return BaseResponse.ok();
		}
	}
}
