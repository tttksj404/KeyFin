package com.finset.key_fin.coaching.client;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.finset.key_fin.coaching.dto.ChartCreated;
import com.finset.key_fin.coaching.dto.ChartHint;

/** 차트 생성은 백엔드 토큰 전용이고, 조회는 X-Coaching-User 의 소유자만 200 이다. */
@Component
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
public class CoachingChartClient {

	private static final String CREATE_PATH = "/v1/charts/budget-forecast";
	private static final String HTML_PATH = "/v1/charts/{chartId}/html";
	private static final String IDEMPOTENCY_KEY = "Idempotency-Key";
	private static final String USER_HEADER = "X-Coaching-User";

	private final RestClient coachingRestClient;

	public CoachingChartClient(@Qualifier("coachingRestClient") RestClient coachingRestClient) {
		this.coachingRestClient = coachingRestClient;
	}

	public ChartCreated create(long userId, ChartHint hint, String idempotencyKey) {
		return coachingRestClient.post()
				.uri(CREATE_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.header(IDEMPOTENCY_KEY, idempotencyKey)
				.header(USER_HEADER, String.valueOf(userId))
				.body(hint)
				.retrieve()
				.body(ChartCreated.class);
	}

	public String html(long userId, String chartId) {
		return coachingRestClient.get()
				.uri(HTML_PATH, chartId)
				.accept(MediaType.TEXT_HTML)
				.header(USER_HEADER, String.valueOf(userId))
				.retrieve()
				.body(String.class);
	}
}
