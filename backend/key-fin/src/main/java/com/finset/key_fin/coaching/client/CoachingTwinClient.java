package com.finset.key_fin.coaching.client;

import java.util.UUID;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.finset.key_fin.coaching.dto.FdtBootstrap;
import com.finset.key_fin.coaching.dto.TwinIdentity;

/** 코칭 API 에 Twin 을 세운다. 원장이 바뀔 때마다 전체 Bootstrap 을 다시 보낸다. */
@Component
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
public class CoachingTwinClient {

	private static final String TWIN_PATH = "/v1/twin";
	private static final String IDEMPOTENCY_KEY = "Idempotency-Key";
	private static final String USER_HEADER = "X-Coaching-User";

	private final RestClient coachingRestClient;

	public CoachingTwinClient(@Qualifier("coachingRestClient") RestClient coachingRestClient) {
		this.coachingRestClient = coachingRestClient;
	}

	public TwinIdentity create(long userId, FdtBootstrap bootstrap) {
		return create(userId, bootstrap, UUID.randomUUID().toString());
	}

	/** 같은 요청을 재시도할 때만 같은 키를 넘긴다. 원장이 바뀌면 새 키여야 한다. */
	public TwinIdentity create(long userId, FdtBootstrap bootstrap, String idempotencyKey) {
		if (bootstrap == null || bootstrap.transactions().isEmpty()) {
			throw new IllegalArgumentException("Bootstrap 에는 거래가 최소 1건 필요합니다.");
		}
		return coachingRestClient.post()
				.uri(TWIN_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.header(IDEMPOTENCY_KEY, idempotencyKey)
				.header(USER_HEADER, String.valueOf(userId))
				.body(bootstrap)
				.retrieve()
				.body(TwinIdentity.class);
	}
}
