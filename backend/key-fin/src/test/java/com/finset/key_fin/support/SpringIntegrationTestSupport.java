package com.finset.key_fin.support;

import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.MySQLContainer;

import com.finset.key_fin.payment.client.FinanceCardBillingClient;
import com.finset.key_fin.payment.client.FinanceSubscriptionClient;
import com.finset.key_fin.payment.client.FinanceTransferClient;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;

/**
 * 모든 통합 테스트가 한 컨텍스트를 나눠 쓴다. 클래스별 @Import·@MockitoBean·@TestPropertySource 는
 * 컨텍스트를 새로 만들게 하므로 여기서 한 번에 올린다.
 */
@SpringBootTest(properties = {
		"fcm.enabled=true",
		"finance.api.max-attempts=3",
		"finance.api.retry-base-delay=0ms",
		"finance.api.retry-max-delay=0ms",
		"finance.api.retry-time-limit=5s"
})
@AutoConfigureMockMvc
@Import({FixedClockConfig.class, FinanceMockServerConfig.class})
public abstract class SpringIntegrationTestSupport {

	public static final String FINANCE_BASE_URL = "https://finance.test/finance/api/v1";
	public static final String FINANCE_API_KEY = "integration-test-api-key";

	@MockitoBean
	protected FinanceTransferClient financeTransferClient;

	@MockitoBean
	protected FinanceCardBillingClient financeCardBillingClient;

	@MockitoBean
	protected FinanceSubscriptionClient financeSubscriptionClient;

	@MockitoBean
	protected FcmSender sender;

	@MockitoBean
	protected FirebaseApp firebaseApp;

	@MockitoBean
	protected FirebaseMessaging firebaseMessaging;

	@Autowired
	protected TestClock testClock;

	@BeforeEach
	void resetTestClock() {
		testClock.set(FixedClockConfig.NOW);
	}

	@DynamicPropertySource
	static void registerInfrastructure(DynamicPropertyRegistry registry) {
		registry.add("spring.datasource.url", () -> Containers.MYSQL.getJdbcUrl()
				+ "?serverTimezone=Asia/Seoul&characterEncoding=UTF-8");
		registry.add("spring.datasource.username", Containers.MYSQL::getUsername);
		registry.add("spring.datasource.password", Containers.MYSQL::getPassword);
		registry.add("spring.data.redis.host", Containers.REDIS::getHost);
		registry.add("spring.data.redis.port", () -> Containers.REDIS.getMappedPort(6379));
		registry.add("jwt.secret", () -> "integration-test-jwt-secret-0123456789abcdef0123456789abcdef");
		registry.add("finance.api.base-url", () -> FINANCE_BASE_URL);
		registry.add("finance.api.api-key", () -> FINANCE_API_KEY);
	}

	private static final class Containers {
		private static final MySQLContainer<?> MYSQL = new MySQLContainer<>("mysql:8.0")
				.withDatabaseName("keyfin")
				.withUsername("keyfin")
				.withPassword("keyfin")
				.withCommand("--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci",
						"--default-time-zone=+09:00");

		private static final GenericContainer<?> REDIS = new GenericContainer<>("redis:7-alpine")
				.withExposedPorts(6379);

		static {
			// Keep containers alive for cached Spring contexts across test classes.
			// Ryuk cleans them up when the test JVM exits; do not add @Container here.
			MYSQL.start();
			REDIS.start();
		}
	}
}
