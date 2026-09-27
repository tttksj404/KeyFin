package com.finset.key_fin.notification.service;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.notification.dto.response.NotificationListResponse;
import com.finset.key_fin.notification.dto.response.NotificationResponse;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.event.NotificationCreated;
import com.finset.key_fin.notification.exception.NotificationErrorCode;
import com.finset.key_fin.notification.repository.NotificationRepository;
import com.finset.key_fin.user.exception.UserErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class NotificationService {
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private final NotificationRepository repository;
	private final Clock clock;
	private final ApplicationEventPublisher events;

	@Transactional
	public long create(long userId, NotificationType type, String title, String body, String refId,
			boolean requiresAction) {
		if (userId <= 0 || type == null || title == null || title.isBlank()
				|| title.codePointCount(0, title.length()) > 100
				|| (refId != null && refId.codePointCount(0, refId.length()) > 30)
				|| (body != null && body.getBytes(StandardCharsets.UTF_8).length > 65_535)) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		if (!repository.isActiveUser(userId)) {
			throw new BusinessException(UserErrorCode.USER_NOT_FOUND);
		}
		long id = repository.insert(userId, type, title, body, refId, requiresAction,
				LocalDateTime.now(clock.withZone(KST)).truncatedTo(ChronoUnit.SECONDS));
		events.publishEvent(new NotificationCreated(id, userId, type, title, body, refId, requiresAction));
		return id;
	}

	@Transactional(readOnly = true)
	public NotificationListResponse list(long userId, boolean unreadOnly, Long cursor, Integer size) {
		int pageSize = size == null ? 20 : size;
		if ((cursor != null && cursor <= 0) || pageSize < 1 || pageSize > 100) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		var rows = repository.findPage(userId, unreadOnly, cursor, pageSize + 1);
		boolean hasNext = rows.size() > pageSize;
		var page = hasNext ? rows.subList(0, pageSize) : rows;
		return new NotificationListResponse(page.stream().map(NotificationResponse::from).toList(),
				hasNext ? page.getLast().id() : null);
	}

	@Transactional
	public void markRead(long userId, long notificationId) {
		if (notificationId <= 0) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		if (repository.markRead(userId, notificationId) == 0 && !repository.existsOwned(userId, notificationId)) {
			throw new BusinessException(NotificationErrorCode.NOTIFICATION_NOT_FOUND);
		}
	}
}
