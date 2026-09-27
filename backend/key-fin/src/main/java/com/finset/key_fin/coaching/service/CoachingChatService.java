package com.finset.key_fin.coaching.service;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.ResourceAccessException;

import java.util.regex.Matcher;
import java.util.regex.Pattern;
import com.finset.key_fin.coaching.client.CoachingChartClient;
import com.finset.key_fin.coaching.client.CoachingChatClient;
import com.finset.key_fin.coaching.client.CoachingTwinClient;
import com.finset.key_fin.coaching.dto.ChatHistoryResponse;
import com.finset.key_fin.coaching.dto.ChatReply;
import com.finset.key_fin.coaching.dto.CoachingSessionView;
import com.finset.key_fin.coaching.dto.CoachingTurnReply;
import com.finset.key_fin.coaching.entity.CoachingSession;
import com.finset.key_fin.coaching.exception.CoachingErrorCode;
import com.finset.key_fin.coaching.repository.CoachingSessionRepository;
import com.finset.key_fin.global.exception.BusinessException;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
public class CoachingChatService {

	private static final Pattern ERROR_CODE = Pattern.compile("\"error\"\\s*:\\s*\"([A-Za-z0-9_.-]+)\"");

	private final CoachingSessionRepository sessionRepository;
	private final CoachingChatClient chatClient;
	private final CoachingTwinClient twinClient;
	private final CoachingChartClient chartClient;
	private final CoachingChartStore chartStore;
	private final FdtBootstrapService bootstrapService;
	private final Clock clock;

	public ChatReply chat(long userId, String message) {
		pushTwin(userId);
		CoachingSession session = activeSession(userId);
		CoachingTurnReply turn;
		try {
			turn = send(userId, session, message);
		} catch (HttpClientErrorException e) {
			if (!isSessionClosed(e)) {
				throw rejected(e);
			}
			log.info("코칭 세션 종료로 재생성: userId={}, status={}", userId, e.getStatusCode());
			session = renew(userId, session);
			turn = send(userId, session, message);
		}
		return ChatReply.from(turn, createChart(userId, session, turn));
	}

	/** 시연·새 대화 시작용: 새 코칭 세션을 강제 발급해 이력·되묻기 맥락을 초기화한다. */
	public void reset(long userId) {
		renew(userId, sessionRepository.findByUserId(userId).orElse(null));
	}

	public String chartHtml(long userId, String chartId) {
		try {
			return chartClient.html(userId, chartId);
		} catch (HttpClientErrorException e) {
			if (e.getStatusCode() == HttpStatus.NOT_FOUND) {
				throw new BusinessException(CoachingErrorCode.CHART_NOT_FOUND, e);
			}
			throw rejected(e);
		} catch (HttpServerErrorException | ResourceAccessException e) {
			throw unavailable(e);
		}
	}

	public ChatHistoryResponse history(long userId) {
		LocalDateTime now = LocalDateTime.now(clock);
		return sessionRepository.findByUserId(userId)
				.filter(session -> !session.isExpired(now))
				.map(session -> {
					try {
						return toHistory(userId, chatClient.getSession(userId, session.getSessionId()));
					} catch (HttpClientErrorException e) {
						if (isSessionClosed(e) || e.getStatusCode() == HttpStatus.NOT_FOUND) {
							return ChatHistoryResponse.empty();
						}
						throw unavailable(e);
					} catch (HttpServerErrorException | ResourceAccessException e) {
						throw unavailable(e);
					}
				})
				.orElseGet(ChatHistoryResponse::empty);
	}

	private CoachingSession activeSession(long userId) {
		LocalDateTime now = LocalDateTime.now(clock);
		return sessionRepository.findByUserId(userId)
				.map(session -> session.isExpired(now) ? renew(userId, session) : session)
				.orElseGet(() -> renew(userId, null));
	}

	private CoachingSession renew(long userId, CoachingSession existing) {
		CoachingSessionView created;
		try {
			created = chatClient.createSession(userId);
		} catch (HttpClientErrorException | HttpServerErrorException | ResourceAccessException e) {
			throw unavailable(e);
		}
		LocalDateTime expiresAt = toLocal(created.expiresAt());
		if (existing == null) {
			return sessionRepository.save(CoachingSession.open(userId, created.id(), expiresAt));
		}
		existing.replace(created.id(), expiresAt);
		return sessionRepository.save(existing);
	}

	private void pushTwin(long userId) {
		try {
			twinClient.create(userId, bootstrapService.build(userId));
		} catch (HttpClientErrorException e) {
			log.warn("트윈 거부 — 이전 트윈으로 대화 진행: userId={}, status={}, body={}",
					userId, e.getStatusCode(), e.getResponseBodyAsString());
		} catch (RuntimeException e) {
			log.warn("트윈 전송 실패 — 이전 트윈으로 대화 진행: userId={}, cause={}", userId, e.toString());
		}
	}

	/** 차트는 답변의 부속물이라 실패해도 답변은 그대로 내려준다. 멱등키를 답변 id 로 고정해 재시도가 같은 차트를 받는다. */
	private String createChart(long userId, CoachingSession session, CoachingTurnReply turn) {
		if (turn.chartHint() == null) {
			return null;
		}
		try {
			String chartId = chartClient.create(userId, turn.chartHint(), "chart-" + turn.id()).id();
			chartStore.save(userId, turn.id(), chartId,
					Duration.between(LocalDateTime.now(clock), session.getExpiresAt()));
			return chartId;
		} catch (RuntimeException e) {
			log.warn("차트 생성 실패 — 답변만 전달: userId={}, answerId={}, code={}, cause={}",
					userId, turn.id(), rejectionCode(e), e.toString());
			return null;
		}
	}

	private CoachingTurnReply send(long userId, CoachingSession session, String message) {
		try {
			return chatClient.sendMessage(userId, session.getSessionId(), message);
		} catch (HttpServerErrorException | ResourceAccessException e) {
			throw unavailable(e);
		}
	}

	private ChatHistoryResponse toHistory(long userId, CoachingSessionView view) {
		return new ChatHistoryResponse(
				view.messages().stream()
						.map(m -> new ChatHistoryResponse.Entry(m.role(), m.content(), chartIdOf(userId, m)))
						.toList(),
				toLocal(view.expiresAt()));
	}

	private String chartIdOf(long userId, CoachingSessionView.Message message) {
		if (message.response() == null || message.response().id() == null) {
			return null;
		}
		try {
			return chartStore.find(userId, message.response().id()).orElse(null);
		} catch (RuntimeException e) {
			log.warn("차트 id 조회 실패 — 이력만 전달: userId={}, answerId={}, cause={}", userId, message.response().id(), e.toString());
			return null;
		}
	}

	private LocalDateTime toLocal(double epochSeconds) {
		return LocalDateTime.ofInstant(Instant.ofEpochSecond((long) epochSeconds), clock.getZone());
	}

	private static boolean isSessionClosed(HttpClientErrorException e) {
		return e.getStatusCode() == HttpStatus.GONE || e.getStatusCode() == HttpStatus.CONFLICT;
	}

	/** 코칭 서버가 살아 있는데 요청을 거절한 4xx. 본문은 {"error": code} 한 단어라 그대로 남긴다. */
	private static BusinessException rejected(HttpClientErrorException cause) {
		log.warn("코칭 서버 거절: status={}, code={}", cause.getStatusCode().value(), rejectionCode(cause));
		return new BusinessException(CoachingErrorCode.COACHING_REJECTED, cause);
	}

	private static BusinessException unavailable(Exception cause) {
		if (cause instanceof HttpStatusCodeException http) {
			log.warn("코칭 서버 응답 실패: status={}, code={}", http.getStatusCode().value(), rejectionCode(http));
		}
		return new BusinessException(CoachingErrorCode.COACHING_UNAVAILABLE, cause);
	}

	private static String rejectionCode(Exception cause) {
		if (!(cause instanceof HttpStatusCodeException http)) {
			return null;
		}
		Matcher matcher = ERROR_CODE.matcher(http.getResponseBodyAsString());
		return matcher.find() ? matcher.group(1) : null;
	}
}
