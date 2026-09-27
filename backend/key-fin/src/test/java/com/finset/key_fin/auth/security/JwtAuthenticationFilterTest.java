package com.finset.key_fin.auth.security;

import com.finset.key_fin.auth.exception.AuthErrorCode;
import com.finset.key_fin.auth.exception.JwtAuthenticationException;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.auth.jwt.TokenType;
import com.finset.key_fin.global.exception.BusinessException;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContextHolder;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class JwtAuthenticationFilterTest {

	private JwtTokenProvider jwtTokenProvider;
	private JwtAuthenticationEntryPoint authenticationEntryPoint;
	private FilterChain filterChain;
	private JwtAuthenticationFilter filter;

	@BeforeEach
	void setUp() {
		jwtTokenProvider = mock(JwtTokenProvider.class);
		authenticationEntryPoint = mock(JwtAuthenticationEntryPoint.class);
		filterChain = mock(FilterChain.class);
		filter = new JwtAuthenticationFilter(jwtTokenProvider, authenticationEntryPoint);
	}

	@AfterEach
	void clearSecurityContext() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void continuesWithoutAuthenticationWhenHeaderIsMissing() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest();
		MockHttpServletResponse response = new MockHttpServletResponse();

		filter.doFilter(request, response, filterChain);

		verify(filterChain).doFilter(request, response);
		verify(jwtTokenProvider, never()).getUserId(any(), any());
	}

	@Test
	void createsAuthenticationFromValidAccessToken() throws Exception {
		MockHttpServletRequest request = requestWithBearerToken("valid-token");
		MockHttpServletResponse response = new MockHttpServletResponse();
		when(jwtTokenProvider.getUserId("valid-token", TokenType.ACCESS)).thenReturn(1L);

		filter.doFilter(request, response, filterChain);

		assertThat(SecurityContextHolder.getContext().getAuthentication().getPrincipal()).isEqualTo(1L);
		assertThat(SecurityContextHolder.getContext().getAuthentication().isAuthenticated()).isTrue();
		verify(filterChain).doFilter(request, response);
	}

	@Test
	void delegatesInvalidTokenToAuthenticationEntryPoint() throws Exception {
		MockHttpServletRequest request = requestWithBearerToken("invalid-token");
		MockHttpServletResponse response = new MockHttpServletResponse();
		BusinessException cause = new BusinessException(AuthErrorCode.INVALID_TOKEN);
		when(jwtTokenProvider.getUserId("invalid-token", TokenType.ACCESS)).thenThrow(cause);

		filter.doFilter(request, response, filterChain);

		ArgumentCaptor<AuthenticationException> exceptionCaptor =
				ArgumentCaptor.forClass(AuthenticationException.class);
		verify(authenticationEntryPoint).commence(eq(request), eq(response), exceptionCaptor.capture());
		assertThat(exceptionCaptor.getValue()).isInstanceOf(JwtAuthenticationException.class);
		assertThat(((JwtAuthenticationException) exceptionCaptor.getValue()).getErrorCode())
				.isEqualTo(AuthErrorCode.INVALID_TOKEN);
		verify(filterChain, never()).doFilter(any(), any());
	}

	@Test
	void ignoresNonBearerAuthorizationScheme() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.addHeader(HttpHeaders.AUTHORIZATION, "Basic credentials");
		MockHttpServletResponse response = new MockHttpServletResponse();

		filter.doFilter(request, response, filterChain);

		verify(filterChain).doFilter(request, response);
		verify(jwtTokenProvider, never()).getUserId(any(), any());
	}

	@Test
	void skipsFilterForPublicRefreshEndpoint() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/v1/auth/refresh");
		request.setServletPath("/api/v1/auth/refresh");
		request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer expired-token");
		MockHttpServletResponse response = new MockHttpServletResponse();

		filter.doFilter(request, response, filterChain);

		verify(filterChain).doFilter(request, response);
		verify(jwtTokenProvider, never()).getUserId(any(), any());
	}

	@Test
	void skipsFilterForSwaggerEndpoint() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest("GET", "/v3/api-docs");
		request.setServletPath("/v3/api-docs");
		request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer invalid-token");
		MockHttpServletResponse response = new MockHttpServletResponse();

		filter.doFilter(request, response, filterChain);

		verify(filterChain).doFilter(request, response);
		verify(jwtTokenProvider, never()).getUserId(any(), any());
	}

	private MockHttpServletRequest requestWithBearerToken(String token) {
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer " + token);
		return request;
	}
}
