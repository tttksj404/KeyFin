package com.finset.key_fin.global.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.time.Duration;
import java.util.List;

/**
 * 브라우저에서 실행되는 프론트엔드가 다른 Origin에서 API를 호출할 수 있도록 CORS를 허용한다.
 * SecurityConfig의 cors() 설정이 이 빈을 찾아 사용하므로, 빈이 없으면 preflight 응답에 허용 헤더가 붙지 않는다.
 * 허용 Origin은 CORS_ALLOWED_ORIGINS 환경변수로 배포 환경마다 지정한다.
 */
@Configuration
@EnableConfigurationProperties(CorsProperties.class)
public class CorsConfig {

	private static final List<String> ALLOWED_METHODS =
			List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS");
	private static final Duration PREFLIGHT_MAX_AGE = Duration.ofHours(1);

	@Bean
	public CorsConfigurationSource corsConfigurationSource(CorsProperties properties) {
		CorsConfiguration configuration = new CorsConfiguration();
		// 포트 와일드카드(http://localhost:[*])를 쓰려면 allowedOrigins가 아닌 allowedOriginPatterns가 필요하다.
		configuration.setAllowedOriginPatterns(properties.allowedOrigins());
		configuration.setAllowedMethods(ALLOWED_METHODS);
		configuration.setAllowedHeaders(List.of(CorsConfiguration.ALL));
		configuration.setAllowCredentials(true);
		configuration.setMaxAge(PREFLIGHT_MAX_AGE);

		UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
		source.registerCorsConfiguration("/**", configuration);
		return source;
	}
}
