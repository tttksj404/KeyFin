package com.finset.key_fin.payment.event;

import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionalEventListener;

import com.finset.key_fin.payment.service.ShortageWarningService;
import com.finset.key_fin.transaction.event.AccountWithdrawn;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class ShortageWarningListener {

	private final ShortageWarningService shortageWarningService;

	@Transactional(propagation = Propagation.REQUIRES_NEW)
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void on(AccountWithdrawn event) {
		try {
			shortageWarningService.evaluate(event.userId(), event.accountId());
		} catch (RuntimeException e) {
			log.warn("재부족 경고 평가 실패: userId={}, accountId={}, cause={}",
					event.userId(), event.accountId(), e.toString());
		}
	}
}
