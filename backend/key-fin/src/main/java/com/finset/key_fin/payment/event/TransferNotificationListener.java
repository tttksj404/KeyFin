package com.finset.key_fin.payment.event;

import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionalEventListener;

import com.finset.key_fin.payment.service.TransferNotificationService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class TransferNotificationListener {

	private final TransferNotificationService transferNotificationService;

	@Transactional(propagation = Propagation.REQUIRES_NEW)
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void on(TransferProposed event) {
		try {
			transferNotificationService.notifyProposed(event);
		} catch (RuntimeException e) {
			log.warn("이체 제안 알림 실패: userId={}, toAccountId={}, cause={}",
					event.userId(), event.toAccountId(), e.toString());
		}
	}

	@Transactional(propagation = Propagation.REQUIRES_NEW)
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void on(TransferCompleted event) {
		try {
			transferNotificationService.notifyCompleted(event);
		} catch (RuntimeException e) {
			log.warn("이체 결과 알림 실패: userId={}, transferId={}, status={}, cause={}",
					event.userId(), event.transferId(), event.status(), e.toString());
		}
	}
}
