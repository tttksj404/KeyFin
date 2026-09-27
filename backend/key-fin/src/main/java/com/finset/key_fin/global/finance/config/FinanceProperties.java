package com.finset.key_fin.global.finance.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.net.URI;
import java.time.Duration;
import java.util.Set;

@ConfigurationProperties(prefix = "finance.api")
public record FinanceProperties(
		URI baseUrl,
		String apiKey,
		Duration connectTimeout,
		Duration readTimeout,
		int maxAttempts,
		Duration retryBaseDelay,
		Duration retryMaxDelay,
		Duration retryTimeLimit
) {

	private static final Set<String> SUPPORTED_SCHEMES = Set.of("http", "https");

	public FinanceProperties {
		validateBaseUrl(baseUrl);
		if (apiKey == null || apiKey.isBlank()) {
			throw new IllegalArgumentException("금융망 API Key는 비어 있을 수 없습니다.");
		}
		validateTimeout(connectTimeout, "금융망 연결 Timeout");
		validateTimeout(readTimeout, "금융망 응답 Timeout");
		if (maxAttempts < 1 || maxAttempts > 5) {
			throw new IllegalArgumentException("금융망 최대 시도 횟수는 1회 이상 5회 이하여야 합니다.");
		}
		validateRetryDuration(retryBaseDelay, "금융망 재시도 기본 간격");
		validateRetryDuration(retryMaxDelay, "금융망 재시도 최대 간격");
		validateTimeout(retryTimeLimit, "금융망 재시도 시간 제한");
		if (retryBaseDelay.compareTo(retryMaxDelay) > 0) {
			throw new IllegalArgumentException("금융망 재시도 최대 간격은 기본 간격보다 짧을 수 없습니다.");
		}
	}

	private static void validateBaseUrl(URI baseUrl) {
		if (baseUrl == null || !baseUrl.isAbsolute() || !SUPPORTED_SCHEMES.contains(baseUrl.getScheme())) {
			throw new IllegalArgumentException("금융망 Base URL은 HTTP 또는 HTTPS 절대 주소여야 합니다.");
		}
	}

	private static void validateTimeout(Duration timeout, String name) {
		if (timeout == null || timeout.isZero() || timeout.isNegative()) {
			throw new IllegalArgumentException(name + "은 0보다 커야 합니다.");
		}
	}

	private static void validateRetryDuration(Duration duration, String name) {
		if (duration == null || duration.isNegative()) {
			throw new IllegalArgumentException(name + "은 0 이상이어야 합니다.");
		}
	}

	@Override
	public String toString() {
		return "FinanceProperties[baseUrl=" + baseUrl
				+ ", apiKey=******"
				+ ", connectTimeout=" + connectTimeout
				+ ", readTimeout=" + readTimeout
				+ ", maxAttempts=" + maxAttempts
				+ ", retryBaseDelay=" + retryBaseDelay
				+ ", retryMaxDelay=" + retryMaxDelay
				+ ", retryTimeLimit=" + retryTimeLimit + "]";
	}
}
