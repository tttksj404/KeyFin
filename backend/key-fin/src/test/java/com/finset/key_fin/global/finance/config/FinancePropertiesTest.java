package com.finset.key_fin.global.finance.config;

import org.junit.jupiter.api.Test;

import java.net.URI;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;

class FinancePropertiesTest {

	private static final URI BASE_URL = URI.create("https://finance.example.com/finance/api/v1");
	private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(3);
	private static final Duration READ_TIMEOUT = Duration.ofSeconds(5);
	private static final int MAX_ATTEMPTS = 3;
	private static final Duration RETRY_BASE_DELAY = Duration.ofMillis(100);
	private static final Duration RETRY_MAX_DELAY = Duration.ofSeconds(1);
	private static final Duration RETRY_TIME_LIMIT = Duration.ofSeconds(8);

	@Test
	void createsFinanceProperties() {
		FinanceProperties properties = new FinanceProperties(
				BASE_URL,
				"finance-api-key",
				CONNECT_TIMEOUT,
				READ_TIMEOUT,
				MAX_ATTEMPTS,
				RETRY_BASE_DELAY,
				RETRY_MAX_DELAY,
				RETRY_TIME_LIMIT
		);

		assertThat(properties.baseUrl()).isEqualTo(BASE_URL);
		assertThat(properties.apiKey()).isEqualTo("finance-api-key");
		assertThat(properties.connectTimeout()).isEqualTo(CONNECT_TIMEOUT);
		assertThat(properties.readTimeout()).isEqualTo(READ_TIMEOUT);
		assertThat(properties.maxAttempts()).isEqualTo(MAX_ATTEMPTS);
		assertThat(properties.retryBaseDelay()).isEqualTo(RETRY_BASE_DELAY);
		assertThat(properties.retryMaxDelay()).isEqualTo(RETRY_MAX_DELAY);
		assertThat(properties.retryTimeLimit()).isEqualTo(RETRY_TIME_LIMIT);
		assertThat(properties.toString())
				.doesNotContain("finance-api-key")
				.contains("apiKey=******");
	}

	@Test
	void rejectsRelativeBaseUrl() {
		assertThatIllegalArgumentException().isThrownBy(() -> new FinanceProperties(
				URI.create("/finance"),
				"finance-api-key",
				CONNECT_TIMEOUT,
				READ_TIMEOUT,
				MAX_ATTEMPTS,
				RETRY_BASE_DELAY,
				RETRY_MAX_DELAY,
				RETRY_TIME_LIMIT
		));
	}

	@Test
	void rejectsBlankApiKey() {
		assertThatIllegalArgumentException().isThrownBy(() -> new FinanceProperties(
				BASE_URL,
				" ",
				CONNECT_TIMEOUT,
				READ_TIMEOUT,
				MAX_ATTEMPTS,
				RETRY_BASE_DELAY,
				RETRY_MAX_DELAY,
				RETRY_TIME_LIMIT
		));
	}

	@Test
	void rejectsNonPositiveTimeout() {
		assertThatIllegalArgumentException().isThrownBy(() -> new FinanceProperties(
				BASE_URL,
				"finance-api-key",
				Duration.ZERO,
				READ_TIMEOUT,
				MAX_ATTEMPTS,
				RETRY_BASE_DELAY,
				RETRY_MAX_DELAY,
				RETRY_TIME_LIMIT
		));
	}

	@Test
	void rejectsAttemptCountOutsideAllowedRange() {
		assertThatIllegalArgumentException().isThrownBy(() -> new FinanceProperties(
				BASE_URL,
				"finance-api-key",
				CONNECT_TIMEOUT,
				READ_TIMEOUT,
				6,
				RETRY_BASE_DELAY,
				RETRY_MAX_DELAY,
				RETRY_TIME_LIMIT
		));
	}

	@Test
	void rejectsNegativeRetryDelay() {
		assertThatIllegalArgumentException().isThrownBy(() -> new FinanceProperties(
				BASE_URL,
				"finance-api-key",
				CONNECT_TIMEOUT,
				READ_TIMEOUT,
				MAX_ATTEMPTS,
				Duration.ofMillis(-1),
				RETRY_MAX_DELAY,
				RETRY_TIME_LIMIT
		));
	}

	@Test
	void rejectsRetryMaxDelayShorterThanBaseDelay() {
		assertThatIllegalArgumentException().isThrownBy(() -> new FinanceProperties(
				BASE_URL,
				"finance-api-key",
				CONNECT_TIMEOUT,
				READ_TIMEOUT,
				MAX_ATTEMPTS,
				Duration.ofSeconds(2),
				Duration.ofSeconds(1),
				RETRY_TIME_LIMIT
		));
	}
}
