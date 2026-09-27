package com.finset.key_fin.global.finance.config;

import org.junit.jupiter.api.Test;
import org.mockito.MockedConstruction;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.mock.http.client.MockClientHttpRequest;
import org.springframework.mock.http.client.MockClientHttpResponse;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mockConstruction;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withNoContent;

class FinanceClientConfigTest {

	private static final URI BASE_URL = URI.create("https://finance-config.test/custom/api");

	@Test
	void usesConfiguredBaseUrlAndJsonAcceptHeader() {
		RestClient.Builder builder = new FinanceClientConfig().financeRestClient(properties()).mutate();
		MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
		RestClient client = builder.build();
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andExpect(method(HttpMethod.GET))
				.andExpect(header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE))
				.andRespond(withNoContent());

		client.get().uri("/member/search").retrieve().toBodilessEntity();

		server.verify();
	}

	@Test
	void usesConfiguredTimeoutsAndDisablesRedirects() throws Exception {
		FinanceProperties properties = properties();
		List<HttpClient> httpClients = new ArrayList<>();
		try (MockedConstruction<JdkClientHttpRequestFactory> factories = mockConstruction(
				JdkClientHttpRequestFactory.class,
				(factory, context) -> httpClients.add((HttpClient) context.arguments().getFirst()))) {
			RestClient client = new FinanceClientConfig().financeRestClient(properties);

			assertThat(httpClients).hasSize(1);
			assertThat(httpClients.getFirst().connectTimeout()).contains(properties.connectTimeout());
			assertThat(httpClients.getFirst().followRedirects()).isEqualTo(HttpClient.Redirect.NEVER);
			assertThat(factories.constructed()).hasSize(1);
			JdkClientHttpRequestFactory factory = factories.constructed().getFirst();
			verify(factory).setReadTimeout(properties.readTimeout());

			// Verify that RestClient uses the configured factory without opening a connection.
			URI requestUri = URI.create(BASE_URL + "/member/search");
			MockClientHttpRequest request = new MockClientHttpRequest(HttpMethod.GET, requestUri);
			request.setResponse(new MockClientHttpResponse(new byte[0], HttpStatus.NO_CONTENT));
			when(factory.createRequest(requestUri, HttpMethod.GET)).thenReturn(request);

			client.get().uri("/member/search").retrieve().toBodilessEntity();

			verify(factory).createRequest(requestUri, HttpMethod.GET);
			assertThat(request.isExecuted()).isTrue();
		} finally {
			httpClients.forEach(HttpClient::close);
		}
	}

	private FinanceProperties properties() {
		return new FinanceProperties(
				BASE_URL,
				"finance-api-key",
				Duration.ofMillis(730),
				Duration.ofMillis(1270),
				3,
				Duration.ofMillis(100),
				Duration.ofSeconds(1),
				Duration.ofSeconds(8)
		);
	}
}
