package com.finset.key_fin.coaching.config;

import java.net.http.HttpClient;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.client.RestClient;

/** 토큰이 설정되지 않은 환경(배치 미확정·로컬)에서도 애플리케이션이 뜨도록 조건부로 등록한다. */
@Configuration
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
@EnableConfigurationProperties(CoachingProperties.class)
public class CoachingClientConfig {

	@Bean
	public RestClient coachingRestClient(CoachingProperties properties) {
		HttpClient httpClient = HttpClient.newBuilder()
				.connectTimeout(properties.connectTimeout())
				.followRedirects(HttpClient.Redirect.NEVER)
				.build();
		JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
		requestFactory.setReadTimeout(properties.readTimeout());

		return RestClient.builder()
				.baseUrl(properties.baseUrl().toString())
				.defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
				.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.token())
				.requestFactory(requestFactory)
				.build();
	}

	/** 구간 알림 피드백 전용. 동기화 스레드를 막지 않고, 대기열이 차면 그 알림의 피드백만 포기한다. */
	@Bean
	public ThreadPoolTaskExecutor coachingFeedbackExecutor() {
		ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
		executor.setCorePoolSize(2);
		executor.setMaxPoolSize(2);
		executor.setQueueCapacity(50);
		executor.setThreadNamePrefix("coach-feedback-");
		return executor;
	}
}
