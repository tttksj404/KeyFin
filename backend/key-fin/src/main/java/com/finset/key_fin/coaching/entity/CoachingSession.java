package com.finset.key_fin.coaching.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "coaching_sessions")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class CoachingSession {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "user_id", nullable = false)
	private Long userId;

	@Column(name = "session_id", nullable = false, length = 64)
	private String sessionId;

	@Column(name = "expires_at", nullable = false)
	private LocalDateTime expiresAt;

	public static CoachingSession open(long userId, String sessionId, LocalDateTime expiresAt) {
		CoachingSession session = new CoachingSession();
		session.userId = userId;
		session.sessionId = sessionId;
		session.expiresAt = expiresAt;
		return session;
	}

	public void replace(String sessionId, LocalDateTime expiresAt) {
		this.sessionId = sessionId;
		this.expiresAt = expiresAt;
	}

	public boolean isExpired(LocalDateTime now) {
		return !expiresAt.isAfter(now);
	}
}
