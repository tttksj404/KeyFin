package com.finset.key_fin.notification.entity;

import java.time.LocalDateTime;

/** JDBC 조회 모델. 토큰은 발송 경계 안에서만 사용하고 응답/로그에는 노출하지 않는다. */
public record PushDevice(long id, long userId, String installationId, String fcmToken,
		String platform, boolean active, LocalDateTime lastSeenAt) {
	@Override
	public String toString() {
		return "PushDevice[id=" + id + ", userId=" + userId + ", active=" + active + "]";
	}
}
