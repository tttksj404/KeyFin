package com.finset.key_fin.payment.client;

import java.io.IOException;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
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
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.payment.dto.request.FinanceBillingStatementRequest;
import com.finset.key_fin.payment.dto.response.FinanceBillingStatement;
import com.finset.key_fin.payment.dto.response.FinanceBillingStatementsResponse;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
public class FinanceCardBillingRestClient implements FinanceCardBillingClient {

	static final String API_NAME = "inquireBillingStatements";
	private static final String STATEMENT_PATH = "/edu/creditCard/" + API_NAME;
	private static final DateTimeFormatter MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");
	private static final int DATE_LENGTH = 8;

	private final RestClient financeRestClient;
	private final FinanceHeaderFactory headerFactory;
	private final FinanceRetryExecutor retryExecutor;
	private final ObjectMapper objectMapper;

	public FinanceCardBillingRestClient(
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
	public List<FinanceBillingStatement> findBillingStatements(
			String userKey, String cardNo, String cvc, YearMonth from, YearMonth to) {
		if (isBlank(userKey) || isBlank(cardNo) || isBlank(cvc)) {
			throw new IllegalArgumentException("금융망 사용자 키·카드번호·CVC는 비어 있을 수 없습니다.");
		}
		FinanceBillingStatementRequest request = new FinanceBillingStatementRequest(
				headerFactory.create(API_NAME, userKey), cardNo, cvc, from.format(MONTH_FORMAT), to.format(MONTH_FORMAT));
		return retryExecutor.execute("카드 청구서 조회", () -> requestStatements(request));
	}

	private List<FinanceBillingStatement> requestStatements(FinanceBillingStatementRequest request) {
		return financeRestClient.post()
				.uri(STATEMENT_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(response));
	}

	private List<FinanceBillingStatement> parseResponse(
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
		List<FinanceBillingStatement> statements = FinanceHttpSupport
				.convert(objectMapper, root, FinanceBillingStatementsResponse.class)
				.statementsOrEmpty();
		statements.forEach(this::validate);
		return statements;
	}

	private void validate(FinanceBillingStatement statement) {
		if (!isDate(statement.billingDate())
				|| !isNumeric(statement.totalBalance())
				|| isBlank(statement.status())) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
	}

	private static boolean isDate(String value) {
		return value != null && value.length() == DATE_LENGTH && isNumeric(value);
	}

	private static boolean isNumeric(String value) {
		return value != null && !value.isBlank() && value.chars().allMatch(Character::isDigit);
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
