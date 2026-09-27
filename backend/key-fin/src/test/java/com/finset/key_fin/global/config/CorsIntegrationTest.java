package com.finset.key_fin.global.config;

import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class CorsIntegrationTest extends SpringIntegrationTestSupport {

	private static final String SIGNUP_PATH = "/api/v1/auth/signup";

	@Autowired
	private MockMvc mockMvc;

	@Test
	void 로컬_개발_Origin의_preflight를_허용한다() throws Exception {
		mockMvc.perform(options(SIGNUP_PATH)
						.header(HttpHeaders.ORIGIN, "http://localhost:8080")
						.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST")
						.header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "content-type"))
				.andExpect(status().isOk())
				.andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:8080"))
				.andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_CREDENTIALS, "true"));
	}

	@Test
	void 포트가_달라도_localhost_Origin을_허용한다() throws Exception {
		mockMvc.perform(options(SIGNUP_PATH)
						.header(HttpHeaders.ORIGIN, "http://localhost:8081")
						.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST"))
				.andExpect(status().isOk())
				.andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:8081"));
	}

	@Test
	void 인증이_필요한_경로도_preflight는_토큰_없이_통과한다() throws Exception {
		mockMvc.perform(options("/api/v1/links/candidates")
						.header(HttpHeaders.ORIGIN, "http://localhost:8080")
						.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
						.header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "authorization"))
				.andExpect(status().isOk())
				.andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:8080"));
	}

	@Test
	void 허용하지_않은_Origin의_preflight는_거절한다() throws Exception {
		mockMvc.perform(options(SIGNUP_PATH)
						.header(HttpHeaders.ORIGIN, "https://attacker.example.com")
						.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST"))
				.andExpect(status().isForbidden())
				.andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
	}
}
