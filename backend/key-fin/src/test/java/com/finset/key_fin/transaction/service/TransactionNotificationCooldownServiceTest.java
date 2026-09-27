package com.finset.key_fin.transaction.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TransactionNotificationCooldownServiceTest {

	private StringRedisTemplate redisTemplate;
	private ValueOperations<String, String> values;
	private TransactionNotificationCooldownService cooldown;

	@BeforeEach
	@SuppressWarnings("unchecked")
	void setUp() {
		redisTemplate = mock(StringRedisTemplate.class);
		values = mock(ValueOperations.class);
		when(redisTemplate.opsForValue()).thenReturn(values);
		cooldown = new TransactionNotificationCooldownService(redisTemplate);
	}

	@Test
	void 일괄_정리_알림은_사용자와_날짜로_구분한다() {
		LocalDate date = LocalDate.of(2026, 9, 18);
		when(values.setIfAbsent(
				"notification:transaction:cleanup:2026-09-18:1", "1", Duration.ofDays(2)))
				.thenReturn(true);

		assertThat(cooldown.acquireDailyCleanup(1L, date)).isTrue();
		verify(values).setIfAbsent(
				"notification:transaction:cleanup:2026-09-18:1", "1", Duration.ofDays(2));
	}

	@Test
	void 같은_날_같은_사용자는_정리_알림을_한번만_획득한다() {
		LocalDate date = LocalDate.of(2026, 9, 18);
		when(values.setIfAbsent(
				"notification:transaction:cleanup:2026-09-18:1", "1", Duration.ofDays(2)))
				.thenReturn(true, false);

		assertThat(cooldown.acquireDailyCleanup(1L, date)).isTrue();
		assertThat(cooldown.acquireDailyCleanup(1L, date)).isFalse();
	}
}
