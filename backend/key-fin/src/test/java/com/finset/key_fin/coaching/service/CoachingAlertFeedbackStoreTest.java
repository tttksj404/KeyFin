package com.finset.key_fin.coaching.service;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;

import com.finset.key_fin.coaching.dto.CoachFeedbackResponse;
import com.finset.key_fin.coaching.dto.CoachFeedbackResponse.Status;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

class CoachingAlertFeedbackStoreTest extends SpringIntegrationTestSupport {

	@Autowired
	private CoachingAlertFeedbackStore store;

	@Autowired
	private StringRedisTemplate redisTemplate;

	@Test
	void PENDING에서_READY로_바뀌고_하루_TTL이_걸린다() {
		store.pending(9001L, 501L);
		assertThat(store.find(9001L, 501L)).isEqualTo(new CoachFeedbackResponse(Status.PENDING, null));

		store.ready(9001L, 501L, "지금 속도면 주기 끝까지 괜찮아요.");

		assertThat(store.find(9001L, 501L))
				.isEqualTo(new CoachFeedbackResponse(Status.READY, "지금 속도면 주기 끝까지 괜찮아요."));
		assertThat(redisTemplate.getExpire("coaching:alert-feedback:9001:501")).isBetween(86_000L, 86_400L);
	}

	@Test
	void FAILED는_문장을_남기지_않고_다른_사용자나_없는_알림은_NONE이다() {
		store.ready(9002L, 502L, "이전 문장");
		store.failed(9002L, 502L);

		assertThat(store.find(9002L, 502L)).isEqualTo(new CoachFeedbackResponse(Status.FAILED, null));
		assertThat(store.find(9003L, 502L).status()).isEqualTo(Status.NONE);
		assertThat(store.find(9002L, 999L).status()).isEqualTo(Status.NONE);
	}
}
