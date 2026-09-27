package com.finset.key_fin.coaching.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;

import java.net.URI;
import java.time.Duration;

import org.junit.jupiter.api.Test;

class CoachingPropertiesTest {

	private static final String TOKEN = "coaching-backend-token-0123456789abcdef";

	@Test
	void 유효한_설정을_받는다() {
		CoachingProperties properties = properties(URI.create("https://coaching.example.com"), TOKEN);

		assertThat(properties.baseUrl().toString()).isEqualTo("https://coaching.example.com");
		assertThat(properties.readTimeout()).isEqualTo(Duration.ofSeconds(60));
	}

	@Test
	void 토큰이_32자_미만이면_거부한다() {
		assertThatIllegalArgumentException()
				.isThrownBy(() -> properties(URI.create("https://coaching.example.com"), "short-token"));
	}

	@Test
	void 토큰이_없으면_거부한다() {
		assertThatIllegalArgumentException()
				.isThrownBy(() -> properties(URI.create("https://coaching.example.com"), null));
	}

	@Test
	void HTTP가_아닌_주소는_거부한다() {
		assertThatIllegalArgumentException()
				.isThrownBy(() -> properties(URI.create("ftp://coaching.example.com"), TOKEN));
		assertThatIllegalArgumentException()
				.isThrownBy(() -> properties(URI.create("/v1"), TOKEN));
	}

	@Test
	void 타임아웃이_0_이하면_거부한다() {
		assertThatIllegalArgumentException().isThrownBy(() -> new CoachingProperties(
				URI.create("https://coaching.example.com"), TOKEN, Duration.ZERO, Duration.ofSeconds(60)));
	}

	@Test
	void 문자열에_토큰을_노출하지_않는다() {
		String text = properties(URI.create("https://coaching.example.com"), TOKEN).toString();

		assertThat(text).doesNotContain(TOKEN).contains("token=******");
	}

	private CoachingProperties properties(URI baseUrl, String token) {
		return new CoachingProperties(baseUrl, token, Duration.ofSeconds(3), Duration.ofSeconds(60));
	}
}
