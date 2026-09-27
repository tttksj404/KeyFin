package com.finset.key_fin.payment.client;

import java.io.IOException;
import java.util.List;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.client.FinanceHeaderErrors;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceHttpSupport;
import com.finset.key_fin.global.finance.client.FinanceResponseCode;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.dto.request.FinanceHeaderRequest;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.payment.dto.response.FinanceSubscription;
import com.finset.key_fin.payment.dto.response.FinanceSubscriptionListResponse;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
public class FinanceSubscriptionRestClient implements FinanceSubscriptionClient {

	static final String API_NAME = "inquireSubscriptionList";
	private static final String SUBSCRIPTION_LIST_PATH = "/edu/creditCard/" + API_NAME;
	private static final int DATE_LENGTH = 8;

	private final RestClient financeRestClient;
	private final FinanceHeaderFactory headerFactory;
	private final FinanceRetryExecutor retryExecutor;
	private final ObjectMapper objectMapper;

	public FinanceSubscriptionRestClient(
			@Qualifier("financeRestClient")
			RestClient financeRestClient,
			FinanceHeaderFactory headerFactory,
			FinanceRetryExecutor retryExecutor,
			ObjectMapper objectMapper
	) {
		this.financeRestClient = financeRestClient;
		this.headerFactory = headerFactory;
		this.retryExecutor = retryExecutor;
		this.objectMapper = objectMapper;
	}

	@Override
	public List<FinanceSubscription> findSubscriptions(String userKey) {
		if (userKey == null || userKey.isBlank()) {
			throw new IllegalArgumentException("금융망 사용자 키는 비어 있을 수 없습니다.");
		}
		return retryExecutor.execute("정기결제 목록 조회", () -> requestSubscriptions(userKey));
	}

	private List<FinanceSubscription> requestSubscriptions(String userKey) {
		FinanceHeaderRequest request = new FinanceHeaderRequest(headerFactory.create(API_NAME, userKey));
		return financeRestClient.post()
				.uri(SUBSCRIPTION_LIST_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(response));
	}

	private List<FinanceSubscription> parseResponse(
			RestClient.RequestHeadersSpec.ConvertibleClientHttpResponse response
	) throws IOException {
		HttpStatusCode statusCode = response.getStatusCode();
		String body = response.bodyTo(String.class);
		if (FinanceHttpSupport.isRetryableStatus(statusCode)) {
			throw FinanceHttpSupport.retryableResponse(response.getHeaders());
		}

		JsonNode root = FinanceHttpSupport.readTree(objectMapper, body);
		String responseCode = FinanceHttpSupport.headerResponseCode(root);
		if (!statusCode.is2xxSuccessful() || !FinanceResponseCode.SUCCESS.matches(responseCode)) {
			throw FinanceHeaderErrors.map(responseCode);
		}

		FinanceSubscriptionListResponse listResponse =
				FinanceHttpSupport.convert(objectMapper, root, FinanceSubscriptionListResponse.class);
		List<FinanceSubscription> subscriptions = listResponse.subscriptionsOrEmpty();
		subscriptions.forEach(this::validate);
		return subscriptions;
	}

	private void validate(FinanceSubscription subscription) {
		if (isBlank(subscription.subscriptionId())
				|| isBlank(subscription.subscriptionName())
				|| isBlank(subscription.paymentAmount())
				|| isBlank(subscription.billingCycle())
				|| isBlank(subscription.status())
				|| subscription.nextPaymentDate() == null || subscription.nextPaymentDate().length() != DATE_LENGTH) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
