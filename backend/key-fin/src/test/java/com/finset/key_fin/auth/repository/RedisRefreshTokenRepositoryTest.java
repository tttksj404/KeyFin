package com.finset.key_fin.auth.repository;

import com.finset.key_fin.auth.config.JwtProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RedisRefreshTokenRepositoryTest {

	private static final String SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
	private static final long USER_ID = 1L;
	private static final String KEY = "auth:refresh:" + USER_ID;
	private static final String REFRESH_TOKEN = "refresh-token";

	private StringRedisTemplate redisTemplate;
	private ValueOperations<String, String> valueOperations;
	private RedisRefreshTokenRepository repository;

	@SuppressWarnings("unchecked")
	@BeforeEach
	void setUp() {
		redisTemplate = mock(StringRedisTemplate.class);
		valueOperations = mock(ValueOperations.class);
		when(redisTemplate.opsForValue()).thenReturn(valueOperations);

		JwtProperties properties = new JwtProperties(
				SECRET, Duration.ofMinutes(30), Duration.ofDays(14)
		);
		repository = new RedisRefreshTokenRepository(redisTemplate, properties);
	}

	@Test
	void savesHashedTokenWithFourteenDayTtl() {
		repository.save(USER_ID, REFRESH_TOKEN);

		verify(valueOperations).set(
				eq(KEY),
				eq(sha256Of(REFRESH_TOKEN)),
				eq(Duration.ofDays(14))
		);
		assertThat(sha256Of(REFRESH_TOKEN)).isNotEqualTo(REFRESH_TOKEN);
	}

	@Test
	void matchesStoredToken() {
		when(valueOperations.get(KEY)).thenReturn(sha256Of(REFRESH_TOKEN));

		assertThat(repository.matches(USER_ID, REFRESH_TOKEN)).isTrue();
	}

	@Test
	void rejectsDifferentToken() {
		when(valueOperations.get(KEY)).thenReturn(sha256Of(REFRESH_TOKEN));

		assertThat(repository.matches(USER_ID, "different-token")).isFalse();
	}

	@Test
	void returnsFalseWhenTokenIsNotStored() {
		when(valueOperations.get(KEY)).thenReturn(null);

		assertThat(repository.matches(USER_ID, REFRESH_TOKEN)).isFalse();
	}

	@Test
	void replacesExistingTokenUsingSameKey() {
		repository.save(USER_ID, REFRESH_TOKEN);
		repository.save(USER_ID, "new-refresh-token");

		verify(valueOperations).set(KEY, sha256Of(REFRESH_TOKEN), Duration.ofDays(14));
		verify(valueOperations).set(KEY, sha256Of("new-refresh-token"), Duration.ofDays(14));
	}

	@Test
	void deletesStoredToken() {
		repository.delete(USER_ID);

		verify(redisTemplate).delete(KEY);
	}

	@Test
	void rejectsInvalidUserId() {
		assertThatIllegalArgumentException()
				.isThrownBy(() -> repository.save(0L, REFRESH_TOKEN))
				.withMessage("사용자 ID는 0보다 커야 합니다.");
	}

	@Test
	void rejectsBlankRefreshToken() {
		assertThatIllegalArgumentException()
				.isThrownBy(() -> repository.save(USER_ID, " "))
				.withMessage("Refresh Token은 비어 있을 수 없습니다.");
	}

	private String sha256Of(String value) {
		try {
			byte[] digest = java.security.MessageDigest.getInstance("SHA-256")
					.digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
			return java.util.HexFormat.of().formatHex(digest);
		} catch (java.security.NoSuchAlgorithmException exception) {
			throw new IllegalStateException(exception);
		}
	}
}
