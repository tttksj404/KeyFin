package com.finset.key_fin.coaching.service;

import java.time.Duration;
import java.util.Map;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import com.finset.key_fin.coaching.dto.CoachFeedbackResponse;
import com.finset.key_fin.coaching.dto.CoachFeedbackResponse.Status;

/** 구간 알림에 붙는 코치 피드백. 즉시 보여 주는 용도라 알림함과 달리 하루 뒤 사라진다. */
@Component
public class CoachingAlertFeedbackStore {

	private static final String KEY_PREFIX = "coaching:alert-feedback:";
	private static final Duration TTL = Duration.ofHours(24);

	private final StringRedisTemplate redisTemplate;

	public CoachingAlertFeedbackStore(StringRedisTemplate redisTemplate) {
		this.redisTemplate = redisTemplate;
	}

	public void pending(long userId, long notificationId) {
		write(userId, notificationId, Map.of("status", Status.PENDING.name()));
	}

	public void ready(long userId, long notificationId, String text) {
		write(userId, notificationId, Map.of("status", Status.READY.name(), "text", text));
	}

	public void failed(long userId, long notificationId) {
		write(userId, notificationId, Map.of("status", Status.FAILED.name()));
	}

	public CoachFeedbackResponse find(long userId, long notificationId) {
		Map<Object, Object> row = redisTemplate.opsForHash().entries(key(userId, notificationId));
		if (row.isEmpty()) {
			return CoachFeedbackResponse.none();
		}
		Status status = Status.valueOf((String) row.get("status"));
		return new CoachFeedbackResponse(status, status == Status.READY ? (String) row.get("text") : null);
	}

	private void write(long userId, long notificationId, Map<String, String> fields) {
		String key = key(userId, notificationId);
		redisTemplate.delete(key);
		redisTemplate.opsForHash().putAll(key, fields);
		redisTemplate.expire(key, TTL);
	}

	private static String key(long userId, long notificationId) {
		return KEY_PREFIX + userId + ":" + notificationId;
	}
}
