package com.finset.key_fin.auth.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

@ConfigurationProperties(prefix = "jwt")
public record JwtProperties(
		String secret,
		Duration accessTokenExpiration,
		Duration refreshTokenExpiration
) {

	private static final int MIN_SECRET_LENGTH_BYTES = 32;

	public JwtProperties {
		if (secret == null || secret.isBlank()) {
			throw new IllegalArgumentException("JWT Secret은 비어 있을 수 없습니다.");
		}
		if (secret.getBytes(StandardCharsets.UTF_8).length < MIN_SECRET_LENGTH_BYTES) {
			throw new IllegalArgumentException("JWT Secret은 32바이트 이상이어야 합니다.");
		}
		validateExpiration(accessTokenExpiration, "Access Token");
		validateExpiration(refreshTokenExpiration, "Refresh Token");
	}

	private static void validateExpiration(Duration expiration, String tokenType) {
		if (expiration == null || expiration.isZero() || expiration.isNegative()) {
			throw new IllegalArgumentException(tokenType + " 만료 시간은 0보다 커야 합니다.");
		}
	}
}
