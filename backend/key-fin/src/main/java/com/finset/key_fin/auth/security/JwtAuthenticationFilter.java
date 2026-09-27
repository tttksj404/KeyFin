package com.finset.key_fin.auth.security;

import com.finset.key_fin.auth.exception.JwtAuthenticationException;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.auth.jwt.TokenType;
import com.finset.key_fin.global.exception.BusinessException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;
import java.util.Set;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

	private static final String BEARER_PREFIX = "Bearer ";
	private static final Set<String> PUBLIC_AUTH_ENDPOINTS = Set.of(
			"/api/v1/auth/signup",
			"/api/v1/auth/login",
			"/api/v1/auth/refresh"
	);

	private final JwtTokenProvider jwtTokenProvider;
	private final JwtAuthenticationEntryPoint authenticationEntryPoint;

	public JwtAuthenticationFilter(
			JwtTokenProvider jwtTokenProvider,
			JwtAuthenticationEntryPoint authenticationEntryPoint
	) {
		this.jwtTokenProvider = jwtTokenProvider;
		this.authenticationEntryPoint = authenticationEntryPoint;
	}

	@Override
	protected boolean shouldNotFilter(HttpServletRequest request) {
		if (HttpMethod.OPTIONS.matches(request.getMethod())) {
			return true;
		}
		String servletPath = request.getServletPath();
		if (servletPath.startsWith("/v3/api-docs")
				|| servletPath.startsWith("/swagger-ui")) {
			return true;
		}
		return HttpMethod.POST.matches(request.getMethod())
				&& PUBLIC_AUTH_ENDPOINTS.contains(servletPath);
	}

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain
	) throws ServletException, IOException {
		String authorization = request.getHeader(HttpHeaders.AUTHORIZATION);
		if (authorization == null || !hasBearerPrefix(authorization)) {
			filterChain.doFilter(request, response);
			return;
		}

		String accessToken = authorization.substring(BEARER_PREFIX.length()).trim();
		long userId;
		try {
			userId = jwtTokenProvider.getUserId(accessToken, TokenType.ACCESS);
		} catch (BusinessException exception) {
			SecurityContextHolder.clearContext();
			authenticationEntryPoint.commence(
					request,
					response,
					new JwtAuthenticationException(exception.getErrorCode(), exception)
			);
			return;
		}

		UsernamePasswordAuthenticationToken authentication =
				UsernamePasswordAuthenticationToken.authenticated(userId, null, List.of());
		authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));

		SecurityContext securityContext = SecurityContextHolder.createEmptyContext();
		securityContext.setAuthentication(authentication);
		SecurityContextHolder.setContext(securityContext);
		filterChain.doFilter(request, response);
	}

	private boolean hasBearerPrefix(String authorization) {
		return authorization.regionMatches(
				true, 0, BEARER_PREFIX, 0, BEARER_PREFIX.length()
		);
	}
}
