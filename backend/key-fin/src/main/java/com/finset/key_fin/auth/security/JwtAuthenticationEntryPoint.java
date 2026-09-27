package com.finset.key_fin.auth.security;

import com.finset.key_fin.auth.exception.AuthErrorCode;
import com.finset.key_fin.auth.exception.JwtAuthenticationException;
import com.finset.key_fin.global.exception.ErrorCode;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
public class JwtAuthenticationEntryPoint implements AuthenticationEntryPoint {

	private final SecurityErrorResponseWriter responseWriter;

	public JwtAuthenticationEntryPoint(SecurityErrorResponseWriter responseWriter) {
		this.responseWriter = responseWriter;
	}

	@Override
	public void commence(
			HttpServletRequest request,
			HttpServletResponse response,
			AuthenticationException authenticationException
	) throws IOException, ServletException {
		ErrorCode errorCode = authenticationException instanceof JwtAuthenticationException jwtException
				? jwtException.getErrorCode()
				: AuthErrorCode.AUTHENTICATION_REQUIRED;
		responseWriter.write(response, errorCode);
	}
}
