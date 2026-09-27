package com.finset.key_fin.coaching.event;

import java.util.concurrent.RejectedExecutionException;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.task.TaskExecutor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import com.finset.key_fin.budget.event.BudgetAlertCreated;
import com.finset.key_fin.coaching.service.CoachingAlertFeedbackService;
import com.finset.key_fin.coaching.service.CoachingAlertFeedbackStore;

import lombok.extern.slf4j.Slf4j;

/** 알림 푸시를 늦추지 않도록 AI 호출은 동기화 스레드가 아닌 전용 풀에서 한다. */
@Slf4j
@Component
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
public class CoachingAlertFeedbackListener {

	private final CoachingAlertFeedbackService feedbackService;
	private final CoachingAlertFeedbackStore store;
	private final TaskExecutor executor;

	public CoachingAlertFeedbackListener(
			CoachingAlertFeedbackService feedbackService,
			CoachingAlertFeedbackStore store,
			@Qualifier("coachingFeedbackExecutor") TaskExecutor executor
	) {
		this.feedbackService = feedbackService;
		this.store = store;
		this.executor = executor;
	}

	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void on(BudgetAlertCreated alert) {
		try {
			store.pending(alert.userId(), alert.notificationId());
			executor.execute(() -> feedbackService.generate(alert));
		} catch (RejectedExecutionException e) {
			log.warn("코치 피드백 대기열 초과: userId={}, notificationId={}", alert.userId(), alert.notificationId());
			store.failed(alert.userId(), alert.notificationId());
		} catch (RuntimeException e) {
			log.warn("코치 피드백 요청 실패: userId={}, notificationId={}, cause={}",
					alert.userId(), alert.notificationId(), e.toString());
		}
	}
}
