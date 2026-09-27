package com.finset.key_fin.coaching.event;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import java.util.concurrent.RejectedExecutionException;

import org.junit.jupiter.api.Test;
import org.mockito.InOrder;
import org.springframework.core.task.TaskExecutor;

import com.finset.key_fin.budget.entity.BudgetAlertLevel;
import com.finset.key_fin.budget.event.BudgetAlertCreated;
import com.finset.key_fin.coaching.service.CoachingAlertFeedbackService;
import com.finset.key_fin.coaching.service.CoachingAlertFeedbackStore;

class CoachingAlertFeedbackListenerTest {

	private static final BudgetAlertCreated ALERT =
			new BudgetAlertCreated(6L, 1, "외식", 91L, BudgetAlertLevel.REMAINING_20);

	private final CoachingAlertFeedbackService feedbackService = mock(CoachingAlertFeedbackService.class);
	private final CoachingAlertFeedbackStore store = mock(CoachingAlertFeedbackStore.class);

	@Test
	void PENDING을_먼저_쓰고_전용_풀에서_평가를_돌린다() {
		TaskExecutor direct = Runnable::run;
		CoachingAlertFeedbackListener listener = new CoachingAlertFeedbackListener(feedbackService, store, direct);

		listener.on(ALERT);

		InOrder order = inOrder(store, feedbackService);
		order.verify(store).pending(6L, 91L);
		order.verify(feedbackService).generate(ALERT);
	}

	@Test
	void 대기열이_차면_그_알림만_FAILED로_둔다() {
		TaskExecutor full = mock(TaskExecutor.class);
		doThrow(new RejectedExecutionException("full")).when(full).execute(any());
		CoachingAlertFeedbackListener listener = new CoachingAlertFeedbackListener(feedbackService, store, full);

		listener.on(ALERT);

		verify(store).failed(6L, 91L);
		verify(feedbackService, never()).generate(any());
	}
}
