package com.finset.key_fin.support;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

@TestConfiguration
public class FinanceMockServerConfig {

	@Bean
	@Qualifier("financeMockBuilder")
	RestClient.Builder financeMockBuilder() {
		return RestClient.builder().baseUrl(SpringIntegrationTestSupport.FINANCE_BASE_URL);
	}

	@Bean
	MockRestServiceServer financeMockServer(@Qualifier("financeMockBuilder") RestClient.Builder builder) {
		return MockRestServiceServer.bindTo(builder).ignoreExpectOrder(true).build();
	}

	@Bean
	@Primary
	@Qualifier("financeRestClient")
	RestClient financeMockRestClient(
			@Qualifier("financeMockBuilder") RestClient.Builder builder,
			MockRestServiceServer financeMockServer
	) {
		return builder.build();
	}
}
