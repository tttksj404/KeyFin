package com.finset.key_fin.coaching.client;

import java.util.Map;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.finset.key_fin.coaching.dto.EnvelopeReview;

@Component
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
public class CoachingEnvelopeReviewClient {

	private static final String REVIEW_PATH = "/v1/coaching/envelope-reviews";
	private static final String IDEMPOTENCY_KEY = "Idempotency-Key";
	private static final String USER_HEADER = "X-Coaching-User";

	private final RestClient coachingRestClient;

	public CoachingEnvelopeReviewClient(@Qualifier("coachingRestClient") RestClient coachingRestClient) {
		this.coachingRestClient = coachingRestClient;
	}

	public EnvelopeReview review(long userId, String envelope, String tier, String idempotencyKey) {
		return coachingRestClient.post()
				.uri(REVIEW_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.header(IDEMPOTENCY_KEY, idempotencyKey)
				.header(USER_HEADER, String.valueOf(userId))
				.body(Map.of("envelope", envelope, "tier", tier))
				.retrieve()
				.body(EnvelopeReview.class);
	}
}
