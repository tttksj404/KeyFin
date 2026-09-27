package com.finset.key_fin.global.finance.client;

import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.global.finance.dto.request.FinanceRequestHeader;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.net.URI;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;

class FinanceHeaderFactoryTest {

	private static final String API_KEY = "test-api-key";
	private static final String USER_KEY = "test-user-key";

	private FinanceHeaderFactory factory;

	@BeforeEach
	void setUp() {
		FinanceProperties properties = new FinanceProperties(
				URI.create("https://finance.example.com/finance/api/v1"),
				API_KEY,
				Duration.ofSeconds(3),
				Duration.ofSeconds(5),
				3,
				Duration.ZERO,
				Duration.ZERO,
				Duration.ofSeconds(1)
		);
		Clock fixedClock = Clock.fixed(Instant.parse("2026-09-10T05:04:09Z"), ZoneId.of("UTC"));
		factory = new FinanceHeaderFactory(properties, fixedClock);
	}

	@Test
	void 호출_시각을_KST_기준으로_공통_Header에_채운다() {
		FinanceRequestHeader header = factory.create("inquireDemandDepositAccountList", USER_KEY);

		assertThat(header.apiName()).isEqualTo("inquireDemandDepositAccountList");
		assertThat(header.apiServiceCode()).isEqualTo("inquireDemandDepositAccountList");
		assertThat(header.transmissionDate()).isEqualTo("20260910");
		assertThat(header.transmissionTime()).isEqualTo("140409");
		assertThat(header.institutionCode()).isEqualTo("00100");
		assertThat(header.fintechAppNo()).isEqualTo("001");
		assertThat(header.apiKey()).isEqualTo(API_KEY);
		assertThat(header.userKey()).isEqualTo(USER_KEY);
	}

	@Test
	void 기관거래고유번호는_전송일시_14자리와_일련번호_6자리로_20자리를_만든다() {
		FinanceRequestHeader header = factory.create("inquireDemandDepositAccountList", USER_KEY);

		assertThat(header.institutionTransactionUniqueNo())
				.hasSize(20)
				.startsWith("20260910140409")
				.matches("\\d{20}");
	}

	@Test
	void 비밀값은_toString에_노출하지_않는다() {
		FinanceRequestHeader header = factory.create("inquireDemandDepositAccountList", USER_KEY);

		assertThat(header.toString())
				.doesNotContain(API_KEY)
				.doesNotContain(USER_KEY)
				.contains("apiKey=******")
				.contains("userKey=******");
	}

	@Test
	void API_이름과_사용자_키는_비어_있을_수_없다() {
		assertThatIllegalArgumentException().isThrownBy(() -> factory.create(" ", USER_KEY));
		assertThatIllegalArgumentException().isThrownBy(() -> factory.create("inquireDemandDepositAccountList", null));
	}
}
