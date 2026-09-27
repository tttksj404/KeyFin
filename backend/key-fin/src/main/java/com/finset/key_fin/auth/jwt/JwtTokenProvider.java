package com.finset.key_fin.auth.jwt;

import com.finset.key_fin.auth.config.JwtProperties;
import com.finset.key_fin.auth.exception.AuthErrorCode;
import com.finset.key_fin.global.exception.BusinessException;
import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.JWSSigner;
import com.nimbusds.jose.JWSVerifier;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.text.ParseException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

@Component
public class JwtTokenProvider {

	private static final String ISSUER = "keyfin";
	private static final String TOKEN_TYPE_CLAIM = "token_type";

	private final JwtProperties properties;
	private final Clock clock;
	private final JWSSigner signer;
	private final JWSVerifier verifier;

	public JwtTokenProvider(JwtProperties properties, Clock clock) {
		this.properties = properties;
		this.clock = clock;

		byte[] secret = properties.secret().getBytes(StandardCharsets.UTF_8);
		try {
			this.signer = new MACSigner(secret);
			this.verifier = new MACVerifier(secret);
		} catch (JOSEException exception) {
			throw new IllegalArgumentException("JWT Secret으로 서명 도구를 생성할 수 없습니다.", exception);
		}
	}

	public String generateAccessToken(long userId) {
		return generateToken(userId, TokenType.ACCESS, properties.accessTokenExpiration());
	}

	public String generateRefreshToken(long userId) {
		return generateToken(userId, TokenType.REFRESH, properties.refreshTokenExpiration());
	}

	public void validateToken(String token, TokenType expectedType) {
		parseAndValidate(token, expectedType);
	}

	public long getUserId(String token, TokenType expectedType) {
		return parseAndValidate(token, expectedType).userId();
	}

	private String generateToken(long userId, TokenType tokenType, Duration expiration) {
		if (userId <= 0) {
			throw new IllegalArgumentException("사용자 ID는 0보다 커야 합니다.");
		}

		Instant issuedAt = clock.instant();
		Instant expiresAt = issuedAt.plus(expiration);
		JWTClaimsSet claims = new JWTClaimsSet.Builder()
				.jwtID(UUID.randomUUID().toString())
				.issuer(ISSUER)
				.subject(Long.toString(userId))
				.issueTime(Date.from(issuedAt))
				.expirationTime(Date.from(expiresAt))
				.claim(TOKEN_TYPE_CLAIM, tokenType.name())
				.build();
		SignedJWT signedJwt = new SignedJWT(
				new JWSHeader.Builder(JWSAlgorithm.HS256)
						.type(JOSEObjectType.JWT)
						.build(),
				claims
		);

		try {
			signedJwt.sign(signer);
			return signedJwt.serialize();
		} catch (JOSEException exception) {
			throw new IllegalStateException("JWT 서명 생성에 실패했습니다.", exception);
		}
	}

	private ValidatedToken parseAndValidate(String token, TokenType expectedType) {
		if (expectedType == null) {
			throw new BusinessException(AuthErrorCode.INVALID_TOKEN);
		}

		AuthErrorCode invalidTokenError = expectedType == TokenType.REFRESH
				? AuthErrorCode.INVALID_REFRESH_TOKEN
				: AuthErrorCode.INVALID_TOKEN;
		if (token == null || token.isBlank()) {
			throw new BusinessException(invalidTokenError);
		}

		try {
			SignedJWT signedJwt = SignedJWT.parse(token);
			if (!JWSAlgorithm.HS256.equals(signedJwt.getHeader().getAlgorithm())
					|| !signedJwt.verify(verifier)) {
				throw new BusinessException(invalidTokenError);
			}

			JWTClaimsSet claims = signedJwt.getJWTClaimsSet();
			if (!ISSUER.equals(claims.getIssuer())) {
				throw new BusinessException(invalidTokenError);
			}

			Date expirationTime = claims.getExpirationTime();
			if (expirationTime == null) {
				throw new BusinessException(invalidTokenError);
			}
			if (!expirationTime.toInstant().isAfter(clock.instant())) {
				throw new BusinessException(AuthErrorCode.EXPIRED_TOKEN);
			}

			String tokenType = claims.getStringClaim(TOKEN_TYPE_CLAIM);
			if (!expectedType.name().equals(tokenType)) {
				throw new BusinessException(invalidTokenError);
			}

			long userId = Long.parseLong(claims.getSubject());
			if (userId <= 0) {
				throw new BusinessException(invalidTokenError);
			}
			return new ValidatedToken(userId);
		} catch (BusinessException exception) {
			throw exception;
		} catch (ParseException | JOSEException | IllegalArgumentException exception) {
			throw new BusinessException(invalidTokenError, exception);
		}
	}

	private record ValidatedToken(long userId) {
	}
}
