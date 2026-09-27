package com.finset.key_fin.auth.repository;

import com.finset.key_fin.auth.config.JwtProperties;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;

@Repository
public class RedisRefreshTokenRepository implements RefreshTokenRepository {

	private static final String KEY_PREFIX = "auth:refresh:";
	private static final String HASH_ALGORITHM = "SHA-256";

	private final StringRedisTemplate redisTemplate;
	private final Duration refreshTokenExpiration;

	public RedisRefreshTokenRepository(
			StringRedisTemplate redisTemplate,
			JwtProperties jwtProperties
	) {
		this.redisTemplate = redisTemplate;
		this.refreshTokenExpiration = jwtProperties.refreshTokenExpiration();
	}

	@Override
	public void save(long userId, String refreshToken) {
		validateUserId(userId);
		validateRefreshToken(refreshToken);

		redisTemplate.opsForValue().set(
				createKey(userId),
				hash(refreshToken),
				refreshTokenExpiration
		);
	}

	@Override
	public boolean matches(long userId, String refreshToken) {
		validateUserId(userId);
		validateRefreshToken(refreshToken);

		String storedHash = redisTemplate.opsForValue().get(createKey(userId));
		if (storedHash == null) {
			return false;
		}

		byte[] storedHashBytes = storedHash.getBytes(StandardCharsets.US_ASCII);
		byte[] requestedHashBytes = hash(refreshToken).getBytes(StandardCharsets.US_ASCII);
		return MessageDigest.isEqual(storedHashBytes, requestedHashBytes);
	}

	@Override
	public void delete(long userId) {
		validateUserId(userId);
		redisTemplate.delete(createKey(userId));
	}

	private String createKey(long userId) {
		return KEY_PREFIX + userId;
	}

	private String hash(String refreshToken) {
		try {
			MessageDigest messageDigest = MessageDigest.getInstance(HASH_ALGORITHM);
			byte[] digest = messageDigest.digest(refreshToken.getBytes(StandardCharsets.UTF_8));
			return HexFormat.of().formatHex(digest);
		} catch (NoSuchAlgorithmException exception) {
			throw new IllegalStateException("SHA-256 해시 알고리즘을 사용할 수 없습니다.", exception);
		}
	}

	private void validateUserId(long userId) {
		if (userId <= 0) {
			throw new IllegalArgumentException("사용자 ID는 0보다 커야 합니다.");
		}
	}

	private void validateRefreshToken(String refreshToken) {
		if (refreshToken == null || refreshToken.isBlank()) {
			throw new IllegalArgumentException("Refresh Token은 비어 있을 수 없습니다.");
		}
	}
}
