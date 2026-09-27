package com.finset.key_fin.auth.jwt;

import com.finset.key_fin.auth.config.JwtProperties;
import com.finset.key_fin.auth.exception.AuthErrorCode;
import com.finset.key_fin.global.exception.BusinessException;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtTokenProviderTest {

	private static final String SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
	private static final Instant NOW = Instant.parse("2026-09-09T00:00:00Z");
	private static final long USER_ID = 1L;

	private JwtProperties properties;
	private JwtTokenProvider tokenProvider;

	@BeforeEach
	void setUp() {
		properties = new JwtProperties(SECRET, Duration.ofMinutes(30), Duration.ofDays(14));
		tokenProvider = new JwtTokenProvider(properties, Clock.fixed(NOW, ZoneOffset.UTC));
	}

	@Test
	void generatesAccessTokenWithRequiredClaims() throws Exception {
		String token = tokenProvider.generateAccessToken(USER_ID);

		JWTClaimsSet claims = SignedJWT.parse(token).getJWTClaimsSet();
		assertThat(claims.getIssuer()).isEqualTo("keyfin");
		assertThat(claims.getSubject()).isEqualTo(Long.toString(USER_ID));
		assertThat(claims.getStringClaim("token_type")).isEqualTo("ACCESS");
		assertThat(claims.getIssueTime().toInstant()).isEqualTo(NOW);
		assertThat(claims.getExpirationTime().toInstant()).isEqualTo(NOW.plus(Duration.ofMinutes(30)));
	}

	@Test
	void generatesRefreshTokenWithFourteenDayExpiration() throws Exception {
		String token = tokenProvider.generateRefreshToken(USER_ID);

		JWTClaimsSet claims = SignedJWT.parse(token).getJWTClaimsSet();
		assertThat(claims.getJWTID()).isNotBlank();
		assertThat(claims.getStringClaim("token_type")).isEqualTo("REFRESH");
		assertThat(claims.getExpirationTime().toInstant()).isEqualTo(NOW.plus(Duration.ofDays(14)));
	}

	@Test
	void generatesUniqueRefreshTokensAtSameInstant() {
		String firstToken = tokenProvider.generateRefreshToken(USER_ID);
		String secondToken = tokenProvider.generateRefreshToken(USER_ID);

		assertThat(firstToken).isNotEqualTo(secondToken);
	}

	@Test
	void extractsUserIdFromValidToken() {
		String token = tokenProvider.generateAccessToken(USER_ID);

		assertThat(tokenProvider.getUserId(token, TokenType.ACCESS)).isEqualTo(USER_ID);
	}

	@Test
	void rejectsTamperedToken() {
		String token = tokenProvider.generateAccessToken(USER_ID);
		String tamperedToken = tamperSignature(token);

		assertErrorCode(
				() -> tokenProvider.validateToken(tamperedToken, TokenType.ACCESS),
				AuthErrorCode.INVALID_TOKEN
		);
	}

	@Test
	void rejectsExpiredToken() {
		String token = tokenProvider.generateAccessToken(USER_ID);
		Clock afterExpiration = Clock.fixed(NOW.plus(Duration.ofMinutes(31)), ZoneOffset.UTC);
		JwtTokenProvider expiredTokenProvider = new JwtTokenProvider(properties, afterExpiration);

		assertErrorCode(
				() -> expiredTokenProvider.validateToken(token, TokenType.ACCESS),
				AuthErrorCode.EXPIRED_TOKEN
		);
	}

	@Test
	void rejectsTokenWithDifferentPurpose() {
		String refreshToken = tokenProvider.generateRefreshToken(USER_ID);

		assertErrorCode(
				() -> tokenProvider.validateToken(refreshToken, TokenType.ACCESS),
				AuthErrorCode.INVALID_TOKEN
		);
	}

	@Test
	void rejectsMalformedToken() {
		assertErrorCode(
				() -> tokenProvider.validateToken("not-a-jwt", TokenType.ACCESS),
				AuthErrorCode.INVALID_TOKEN
		);
	}

	@Test
	void rejectsMalformedRefreshTokenWithRefreshTokenError() {
		assertErrorCode(
				() -> tokenProvider.validateToken("not-a-jwt", TokenType.REFRESH),
				AuthErrorCode.INVALID_REFRESH_TOKEN
		);
	}

	@Test
	void requiresSecretOfAtLeastThirtyTwoBytes() {
		assertThatIllegalArgumentException()
				.isThrownBy(() -> new JwtProperties(
						"too-short", Duration.ofMinutes(30), Duration.ofDays(14)
				))
				.withMessage("JWT Secret은 32바이트 이상이어야 합니다.");
	}

	private void assertErrorCode(Runnable action, AuthErrorCode expectedErrorCode) {
		BusinessException exception = assertThrows(BusinessException.class, action::run);
		assertThat(exception.getErrorCode()).isEqualTo(expectedErrorCode);
	}

	private String tamperSignature(String token) {
		String[] parts = token.split("\\.");
		char firstCharacter = parts[2].charAt(0);
		parts[2] = (firstCharacter == 'A' ? 'B' : 'A') + parts[2].substring(1);
		return String.join(".", parts);
	}
}
