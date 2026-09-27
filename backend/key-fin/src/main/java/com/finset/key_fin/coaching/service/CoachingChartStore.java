package com.finset.key_fin.coaching.service;

import java.time.Duration;
import java.util.Optional;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/** 답변 id → 차트 id. 코칭 서버 이력에는 차트 id 가 없어 세션이 살아 있는 동안만 여기서 잇는다. */
@Component
public class CoachingChartStore {

	private static final String KEY_PREFIX = "coaching:chart:";
	private static final Duration MIN_TTL = Duration.ofMinutes(1);

	private final StringRedisTemplate redisTemplate;

	public CoachingChartStore(StringRedisTemplate redisTemplate) {
		this.redisTemplate = redisTemplate;
	}

	public void save(long userId, String answerId, String chartId, Duration ttl) {
		Duration effective = ttl.compareTo(MIN_TTL) < 0 ? MIN_TTL : ttl;
		redisTemplate.opsForValue().set(key(userId, answerId), chartId, effective);
	}

	public Optional<String> find(long userId, String answerId) {
		return Optional.ofNullable(redisTemplate.opsForValue().get(key(userId, answerId)));
	}

	private static String key(long userId, String answerId) {
		return KEY_PREFIX + userId + ":" + answerId;
	}
}
