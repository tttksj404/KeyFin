package com.finset.key_fin.payment.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

import java.net.URI;
import java.time.Duration;
import java.time.LocalDate;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.payment.dto.response.FinanceSubscription;

import tools.jackson.databind.json.JsonMapper;

class FinanceSubscriptionRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String LIST_URL = BASE_URL + "/edu/creditCard/inquireSubscriptionList";
	private static final String USER_KEY = "test-user-key";
	private static final String SUCCESS_HEADER = """
			"Header": {"responseCode": "H0000", "responseMessage": "정상처리 되었습니다."}
			""";

	private MockRestServiceServer server;
	private FinanceSubscriptionRestClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
		server = MockRestServiceServer.bindTo(builder).build();
		FinanceProperties properties = new FinanceProperties(
				URI.create(BASE_URL), "test-api-key",
				Duration.ofSeconds(3), Duration.ofSeconds(5), 3, Duration.ZERO, Duration.ZERO, Duration.ofSeconds(1));
		client = new FinanceSubscriptionRestClient(
				builder.build(), new FinanceHeaderFactory(properties), new FinanceRetryExecutor(properties),
				JsonMapper.builder().build());
	}

	@Test
	@DisplayName("공통 Header로 정기결제 목록을 조회해 REC.subscriptions를 돌려준다")
	void findsSubscriptions() {
		server.expect(requestTo(LIST_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(jsonPath("$.Header.apiName").value("inquireSubscriptionList"))
				.andExpect(jsonPath("$.Header.userKey").value(USER_KEY))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": {
								  "totalMonthlyAmount": "8900", "activeCount": "1",
								  "subscriptions": [
								    {"subscriptionId": "SUB20260913205959144", "subscriptionName": "FLO", "paymentAmount": "8900",
								     "billingCycle": "MONTHLY", "dailyAmount": null, "nextPaymentDate": "20261013", "status": "ACTIVE"},
								    {"subscriptionId": "SUB20260901000000001", "subscriptionName": "일간뉴스", "paymentAmount": "300",
								     "billingCycle": "DAILY", "dailyAmount": "300", "nextPaymentDate": "20260914", "status": "PAUSED"}
								  ]
								}}
								"""));

		List<FinanceSubscription> subscriptions = client.findSubscriptions(USER_KEY);

		assertThat(subscriptions).hasSize(2);
		FinanceSubscription flo = subscriptions.get(0);
		assertThat(flo.subscriptionId()).isEqualTo("SUB20260913205959144");
		assertThat(flo.amount()).isEqualTo(8900L);
		assertThat(flo.isMonthly()).isTrue();
		assertThat(flo.isActive()).isTrue();
		assertThat(flo.nextPayment()).isEqualTo(LocalDate.of(2026, 10, 13));
		assertThat(subscriptions.get(1).isMonthly()).isFalse();
		assertThat(subscriptions.get(1).isActive()).isFalse();
		server.verify();
	}

	@Test
	@DisplayName("구독이 없어 subscriptions가 비어 있으면 빈 목록")
	void returnsEmptyWhenNoSubscriptions() {
		server.expect(requestTo(LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + ", \"REC\": {\"totalMonthlyAmount\": \"0\", \"activeCount\": \"0\", \"subscriptions\": []}}"));

		assertThat(client.findSubscriptions(USER_KEY)).isEmpty();
		server.verify();
	}

	@Test
	@DisplayName("사용자 키가 무효하면 금융망 공통 오류(USER_KEY_INVALID)로 매핑된다")
	void mapsInvalidUserKey() {
		server.expect(requestTo(LIST_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"Header\": {\"responseCode\": \"H1009\", \"responseMessage\": \"USER_KEY가 유효하지 않습니다.\"}}"));

		assertThatThrownBy(() -> client.findSubscriptions(USER_KEY))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(FinanceErrorCode.USER_KEY_INVALID);
		server.verify();
	}

	@Test
	@DisplayName("필수 필드가 빠진 응답은 INVALID_RESPONSE")
	void rejectsMalformedSubscription() {
		server.expect(requestTo(LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": {"subscriptions": [{"subscriptionId": "SUB1", "subscriptionName": "FLO", "paymentAmount": "8900",
								  "billingCycle": "MONTHLY", "nextPaymentDate": "2026-10-13", "status": "ACTIVE"}]}}
								"""));

		assertThatThrownBy(() -> client.findSubscriptions(USER_KEY))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(FinanceErrorCode.INVALID_RESPONSE);
	}
}
