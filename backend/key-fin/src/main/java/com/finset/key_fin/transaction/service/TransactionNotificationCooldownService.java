package com.finset.key_fin.transaction.service;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.LocalDate;


@Component
public class TransactionNotificationCooldownService {

	private static final String CLEANUP_KEY_PREFIX = "notification:transaction:cleanup:";
	private static final Duration CLEANUP_TTL = Duration.ofDays(2);

	private final StringRedisTemplate redisTemplate;

	public TransactionNotificationCooldownService(StringRedisTemplate redisTemplate) {
		this.redisTemplate = redisTemplate;
	}

	public boolean acquireDailyCleanup(long userId, LocalDate date) {
		String key = CLEANUP_KEY_PREFIX + date + ":" + userId;
		return Boolean.TRUE.equals(redisTemplate.opsForValue().setIfAbsent(key, "1", CLEANUP_TTL));
	}
}
