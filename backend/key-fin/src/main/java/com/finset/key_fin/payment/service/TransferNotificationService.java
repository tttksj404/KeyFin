package com.finset.key_fin.payment.service;

import org.springframework.stereotype.Service;

import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.event.TransferCompleted;
import com.finset.key_fin.payment.event.TransferProposed;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class TransferNotificationService {

	private final NotificationService notificationService;

	public void notifyProposed(TransferProposed event) {
		notificationService.create(event.userId(), NotificationType.TRANSFER_REQUEST,
				"자동이체 준비 승인 필요", "자동이체가 준비되었습니다. 승인해주세요.",
				String.valueOf(event.toAccountId()), true);
	}

	public void notifyCompleted(TransferCompleted event) {
		if (event.status() == TransferStatus.EXECUTED) {
			notificationService.create(event.userId(), NotificationType.TRANSFER_REQUEST,
					"결제 금액을 준비했어요", "자동이체가 완료되었습니다.",
					String.valueOf(event.transferId()), false);
			return;
		}
		if (event.status() == TransferStatus.FAILED) {
			notificationService.create(event.userId(), NotificationType.TRANSFER_REQUEST,
					"이체하지 못했어요", "자동이체에 실패했습니다. 확인해주세요.",
					String.valueOf(event.transferId()), true);
		}
	}
}
