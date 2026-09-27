package com.finset.key_fin.budget.event;

import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionalEventListener;

import com.finset.key_fin.budget.service.BudgetNotificationService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class BudgetAlertListener {

	private final BudgetNotificationService budgetNotificationService;

	@Transactional(propagation = Propagation.REQUIRES_NEW)
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void on(EnvelopeSpendingChanged event) {
		try {
			budgetNotificationService.evaluate(event.userId(), event.envelopeId(), event.restoredKrw());
		} catch (RuntimeException e) {
			log.warn("예산 구간 알림 평가 실패: userId={}, envelopeId={}, cause={}",
					event.userId(), event.envelopeId(), e.toString());
		}
	}
}
