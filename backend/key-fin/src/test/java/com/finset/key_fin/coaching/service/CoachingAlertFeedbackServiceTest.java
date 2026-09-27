package com.finset.key_fin.coaching.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import org.junit.jupiter.api.Test;
import org.springframework.web.client.ResourceAccessException;

import com.finset.key_fin.budget.entity.BudgetAlertLevel;
import com.finset.key_fin.budget.event.BudgetAlertCreated;
import com.finset.key_fin.coaching.client.CoachingEnvelopeReviewClient;
import com.finset.key_fin.coaching.client.CoachingTwinClient;
import com.finset.key_fin.coaching.dto.EnvelopeReview;
import com.finset.key_fin.coaching.dto.FdtBootstrap;

class CoachingAlertFeedbackServiceTest {

	private static final long USER_ID = 6L;
	private static final BudgetAlertCreated ALERT =
			new BudgetAlertCreated(USER_ID, 4, "취미·여가", 91L, BudgetAlertLevel.EXCEEDED);

	private final CoachingTwinClient twinClient = mock(CoachingTwinClient.class);
	private final FdtBootstrapService bootstrapService = mock(FdtBootstrapService.class);
	private final CoachingEnvelopeReviewClient reviewClient = mock(CoachingEnvelopeReviewClient.class);
	private final CoachingAlertFeedbackStore store = mock(CoachingAlertFeedbackStore.class);
	private final FdtBootstrap bootstrap = mock(FdtBootstrap.class);

	private final CoachingAlertFeedbackService service =
			new CoachingAlertFeedbackService(twinClient, bootstrapService, reviewClient, store);

	@Test
	void 트윈을_보낸_뒤_봉투_평가를_받아_READY로_저장한다() {
		given(bootstrapService.build(USER_ID)).willReturn(bootstrap);
		given(reviewClient.review(USER_ID, "취미·여가", "over", "alert-feedback-91"))
				.willReturn(new EnvelopeReview("이번 주는 취미 지출을 잠깐 쉬어 가자냥."));

		service.generate(ALERT);

		verify(twinClient).create(USER_ID, bootstrap);
		verify(store).ready(USER_ID, 91L, "이번 주는 취미 지출을 잠깐 쉬어 가자냥.");
	}

	@Test
	void 트윈_전송이_실패하면_평가를_부르지_않고_FAILED다() {
		given(bootstrapService.build(USER_ID)).willReturn(bootstrap);
		given(twinClient.create(USER_ID, bootstrap)).willThrow(new ResourceAccessException("timeout"));

		service.generate(ALERT);

		verify(reviewClient, never()).review(anyLong(), anyString(), anyString(), anyString());
		verify(store).failed(USER_ID, 91L);
	}

	@Test
	void 평가가_실패하거나_빈_문장이면_FAILED다() {
		given(bootstrapService.build(USER_ID)).willReturn(bootstrap);
		given(reviewClient.review(USER_ID, "취미·여가", "over", "alert-feedback-91"))
				.willThrow(new ResourceAccessException("timeout"))
				.willReturn(new EnvelopeReview(" "));

		service.generate(ALERT);
		service.generate(ALERT);

		verify(store, org.mockito.Mockito.times(2)).failed(USER_ID, 91L);
		verify(store, never()).ready(anyLong(), anyLong(), anyString());
	}

	@Test
	void 알림_단계를_AI_구간_값으로_바꾼다() {
		assertThat(CoachingAlertFeedbackService.tier(BudgetAlertLevel.REMAINING_50)).isEqualTo("50");
		assertThat(CoachingAlertFeedbackService.tier(BudgetAlertLevel.REMAINING_20)).isEqualTo("20");
		assertThat(CoachingAlertFeedbackService.tier(BudgetAlertLevel.REMAINING_5)).isEqualTo("5");
		assertThat(CoachingAlertFeedbackService.tier(BudgetAlertLevel.EXCEEDED)).isEqualTo("over");
	}
}
