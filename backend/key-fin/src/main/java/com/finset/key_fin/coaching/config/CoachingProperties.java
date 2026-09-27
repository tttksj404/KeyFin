package com.finset.key_fin.coaching.config;

import java.net.URI;
import java.time.Duration;
import java.util.Set;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "coaching.api")
public record CoachingProperties(
		URI baseUrl,
		String token,
		Duration connectTimeout,
		Duration readTimeout
) {

	private static final Set<String> SUPPORTED_SCHEMES = Set.of("http", "https");
	/** 코칭 API 는 32자 이상의 고유 토큰을 요구한다. */
	private static final int MIN_TOKEN_LENGTH = 32;

	public CoachingProperties {
		if (baseUrl == null || !baseUrl.isAbsolute() || !SUPPORTED_SCHEMES.contains(baseUrl.getScheme())) {
			throw new IllegalArgumentException("코칭 API Base URL은 HTTP 또는 HTTPS 절대 주소여야 합니다.");
		}
		if (token == null || token.length() < MIN_TOKEN_LENGTH) {
			throw new IllegalArgumentException("코칭 API 토큰은 " + MIN_TOKEN_LENGTH + "자 이상이어야 합니다.");
		}
		validateTimeout(connectTimeout, "코칭 API 연결 Timeout");
		validateTimeout(readTimeout, "코칭 API 응답 Timeout");
	}

	private static void validateTimeout(Duration timeout, String name) {
		if (timeout == null || timeout.isZero() || timeout.isNegative()) {
			throw new IllegalArgumentException(name + "은 0보다 커야 합니다.");
		}
	}

	@Override
	public String toString() {
		return "CoachingProperties[baseUrl=" + baseUrl
				+ ", token=******"
				+ ", connectTimeout=" + connectTimeout
				+ ", readTimeout=" + readTimeout + "]";
	}
}
