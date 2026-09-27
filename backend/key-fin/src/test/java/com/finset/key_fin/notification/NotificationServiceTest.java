package com.finset.key_fin.notification;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.repository.NotificationRepository;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.context.ApplicationEventPublisher;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class NotificationServiceTest {
	NotificationRepository repository;
	NotificationService service;

	@BeforeEach
	void setUp() {
		repository = mock(NotificationRepository.class);
		service = new NotificationService(repository, Clock.fixed(Instant.parse("2026-09-16T13:00:00Z"), ZoneOffset.UTC),
				mock(ApplicationEventPublisher.class));
	}

	@ParameterizedTest
	@NullAndEmptySource
	@ValueSource(strings = {" ", "\t\n"})
	void rejectsBlankTitleBeforeDatabaseAccess(String title) {
		invalid(() -> service.create(1, NotificationType.WARNING, title, null, null, false));
		verifyNoInteractions(repository);
	}

	@Test
	void rejectsInvalidUserTypeAndColumnLengthsBeforeDatabaseAccess() {
		invalid(() -> service.create(0, NotificationType.WARNING, "title", null, null, false));
		invalid(() -> service.create(1, null, "title", null, null, false));
		invalid(() -> service.create(1, NotificationType.WARNING, "😀".repeat(101), null, null, false));
		invalid(() -> service.create(1, NotificationType.WARNING, "title", null, "가".repeat(31), false));
		invalid(() -> service.create(1, NotificationType.WARNING, "title", "a".repeat(65_536), null, false));
		invalid(() -> service.create(1, NotificationType.WARNING, "title", "가".repeat(21_846), null, false));
		invalid(() -> service.create(1, NotificationType.WARNING, "title", "😀".repeat(16_384), null, false));
		verifyNoInteractions(repository);
	}

	@Test
	void rejectsMissingOrDeletedRecipient() {
		when(repository.isActiveUser(1)).thenReturn(false);
		assertThatThrownBy(() -> service.create(1, NotificationType.WARNING, "title", null, null, false))
				.isInstanceOfSatisfying(BusinessException.class,
						e -> assertThat(e.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verify(repository).isActiveUser(1);
		verifyNoMoreInteractions(repository);
	}

	@Test
	void rejectsInvalidPaginationAndNotificationIdBeforeDatabaseAccess() {
		for (long cursor : new long[]{0, -1}) invalid(() -> service.list(1, false, cursor, null));
		for (int size : new int[]{0, -1, 101}) invalid(() -> service.list(1, false, null, size));
		invalid(() -> service.markRead(1, 0));
		invalid(() -> service.markRead(1, -1));
		verifyNoInteractions(repository);
	}

	private void invalid(Runnable operation) {
		assertThatThrownBy(operation::run).isInstanceOfSatisfying(BusinessException.class,
				e -> assertThat(e.getErrorCode()).isEqualTo(CommonErrorCode.INVALID_INPUT_VALUE));
	}
}
