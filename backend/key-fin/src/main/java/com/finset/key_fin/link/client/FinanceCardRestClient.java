package com.finset.key_fin.link.client;

import com.finset.key_fin.global.finance.client.FinanceResponseCode;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.client.FinanceHttpSupport;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceHeaderErrors;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.dto.request.FinanceHeaderRequest;
import com.finset.key_fin.link.dto.response.FinanceCard;
import com.finset.key_fin.link.dto.response.FinanceCardListResponse;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.util.List;

@Component
public class FinanceCardRestClient implements FinanceCardClient {

	static final String API_NAME = "inquireSignUpCreditCardList";
	private static final String CARD_LIST_PATH = "/edu/creditCard/" + API_NAME;
	private static final int CVC_LENGTH = 3;

	private final RestClient financeRestClient;
	private final FinanceHeaderFactory headerFactory;
	private final FinanceRetryExecutor retryExecutor;
	private final ObjectMapper objectMapper;

	public FinanceCardRestClient(
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
	public List<FinanceCard> findCards(String userKey) {
		if (userKey == null || userKey.isBlank()) {
			throw new IllegalArgumentException("금융망 사용자 키는 비어 있을 수 없습니다.");
		}
		return retryExecutor.execute("카드 목록 조회", () -> requestCards(userKey));
	}

	private List<FinanceCard> requestCards(String userKey) {
		FinanceHeaderRequest request = new FinanceHeaderRequest(headerFactory.create(API_NAME, userKey));
		return financeRestClient.post()
				.uri(CARD_LIST_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(response));
	}

	private List<FinanceCard> parseResponse(
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

		FinanceCardListResponse listResponse =
				FinanceHttpSupport.convert(objectMapper, root, FinanceCardListResponse.class);
		List<FinanceCard> cards = listResponse.cardsOrEmpty();
		cards.forEach(this::validateCard);
		return cards;
	}

	private void validateCard(FinanceCard card) {
		if (isBlank(card.cardNo())
				|| card.cvc() == null || card.cvc().length() != CVC_LENGTH
				|| isBlank(card.cardIssuerCode())
				|| isBlank(card.cardName())
				|| !isWeekday(card.withdrawalDate())) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
	}

	private static boolean isWeekday(String value) {
		return value != null && value.length() == 1 && value.charAt(0) >= '1' && value.charAt(0) <= '7';
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
