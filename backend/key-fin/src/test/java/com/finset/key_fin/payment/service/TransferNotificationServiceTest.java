package com.finset.key_fin.payment.service;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.event.TransferCompleted;
import com.finset.key_fin.payment.event.TransferProposed;

class TransferNotificationServiceTest {

	private static final long USER_ID = 986L;

	private final NotificationService notifications = mock(NotificationService.class);
	private final TransferNotificationService service = new TransferNotificationService(notifications);

	@Test
	@DisplayName("제안 알림은 출금 계좌 ID를 refId로, 승인이 필요한 TRANSFER_REQUEST로 만든다")
	void proposedRequiresAction() {
		service.notifyProposed(new TransferProposed(USER_ID, 9504L));

		verify(notifications).create(eq(USER_ID), eq(NotificationType.TRANSFER_REQUEST),
				eq("자동이체 준비 승인 필요"), eq("자동이체가 준비되었습니다. 승인해주세요."), eq("9504"), eq(true));
	}

	@Test
	@DisplayName("EXECUTED는 제안 ID를 refId로, 행동이 필요 없는 알림을 만든다")
	void executedIsInformational() {
		service.notifyCompleted(new TransferCompleted(USER_ID, 9901L, TransferStatus.EXECUTED));

		verify(notifications).create(eq(USER_ID), eq(NotificationType.TRANSFER_REQUEST),
				eq("결제 금액을 준비했어요"), eq("자동이체가 완료되었습니다."), eq("9901"), eq(false));
	}

	@Test
	@DisplayName("FAILED는 제안 ID를 refId로, 행동이 필요한 알림을 만든다")
	void failedRequiresAction() {
		service.notifyCompleted(new TransferCompleted(USER_ID, 9901L, TransferStatus.FAILED));

		verify(notifications).create(eq(USER_ID), eq(NotificationType.TRANSFER_REQUEST),
				eq("이체하지 못했어요"), eq("자동이체에 실패했습니다. 확인해주세요."), eq("9901"), eq(true));
	}

	@ParameterizedTest
	@EnumSource(value = TransferStatus.class, names = {"PROPOSED", "APPROVED", "CANCELED"})
	@DisplayName("EXECUTED·FAILED 외 상태는 알림을 만들지 않는다")
	void otherStatusesAreSilent(TransferStatus status) {
		service.notifyCompleted(new TransferCompleted(USER_ID, 9901L, status));

		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), anyString(), anyBoolean());
	}
}
