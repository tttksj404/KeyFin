package com.finset.key_fin.global.config;

import java.io.IOException;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.io.support.ResourcePropertySource;
import org.springframework.scheduling.support.CronExpression;

import static org.assertj.core.api.Assertions.assertThat;

class SchedulerCronPropertiesTest {

	private static final Map<String, String> DEFAULTS = Map.of(
			"transaction.sync.cron", "0 * * * * *",
			"transaction.notification.cleanup-cron", "0 0 21 * * *",
			"payment.sync.cron", "0 0 8,17 * * *",
			"payment.transfer-proposal.cron", "0 30 8 * * *",
			"payment.transfer-recover.cron", "0 0/30 * * * *");

	private final StandardEnvironment environment = new StandardEnvironment();

	@BeforeEach
	void loadApplicationProperties() throws IOException {
		environment.getPropertySources().addLast(new ResourcePropertySource("classpath:application.properties"));
	}

	@Test
	void 환경_변수가_없으면_운영_크론이_그대로_쓰인다() {
		DEFAULTS.forEach((key, cron) -> {
			assertThat(environment.getProperty(key)).as(key).isEqualTo(cron);
			assertThat(CronExpression.isValidExpression(cron)).as(key).isTrue();
		});
	}

	@Test
	void 환경_변수가_있으면_그_주기로_바뀐다() {
		environment.getPropertySources().addFirst(new MapPropertySource("env", Map.of(
				"TRANSACTION_SYNC_CRON", "0/30 * * * * *",
				"PAYMENT_SYNC_CRON", "0 */5 * * * *")));

		assertThat(environment.getProperty("transaction.sync.cron")).isEqualTo("0/30 * * * * *");
		assertThat(environment.getProperty("payment.sync.cron")).isEqualTo("0 */5 * * * *");
		assertThat(environment.getProperty("payment.transfer-proposal.cron")).isEqualTo("0 30 8 * * *");
	}
}
