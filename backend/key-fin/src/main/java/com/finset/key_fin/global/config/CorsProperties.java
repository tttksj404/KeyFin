package com.finset.key_fin.global.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;

@ConfigurationProperties(prefix = "cors")
public record CorsProperties(
		List<String> allowedOrigins
) {

	public CorsProperties {
		if (allowedOrigins == null || allowedOrigins.isEmpty()) {
			throw new IllegalArgumentException("CORS 허용 Origin은 하나 이상 설정해야 합니다.");
		}
		if (allowedOrigins.stream().anyMatch(origin -> origin == null || origin.isBlank())) {
			throw new IllegalArgumentException("CORS 허용 Origin은 비어 있을 수 없습니다.");
		}
		allowedOrigins = List.copyOf(allowedOrigins);
	}
}
