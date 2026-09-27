package com.finset.key_fin.transaction.client;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.client.FinanceHeaderErrors;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceHttpSupport;
import com.finset.key_fin.global.finance.client.FinanceResponseCode;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.transaction.dto.finance.request.FinanceCardTransactionRequest;
import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransaction;
import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransactionRecord;
import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransactionResponse;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.List;

@Component
public class FinanceCardTransactionRestClient implements FinanceCardTransactionClient {

	static final String API_NAME = "inquireCreditCardTransactionList";
	private static final String TRANSACTION_LIST_PATH = "/edu/creditCard/" + API_NAME;
	private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.BASIC_ISO_DATE;
	private static final int CVC_LENGTH = 3;

	private final RestClient financeRestClient;
	private final FinanceHeaderFactory headerFactory;
	private final FinanceRetryExecutor retryExecutor;
	private final ObjectMapper objectMapper;

	public FinanceCardTransactionRestClient(
			@Qualifier("financeRestClient") RestClient financeRestClient,
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
	public List<FinanceCardTransaction> findTransactions(
			String userKey,
			String cardNo,
			String cvc,
			LocalDate startDate,
			LocalDate endDate
	) {
		validateRequest(userKey, cardNo, cvc, startDate, endDate);
		return retryExecutor.execute("카드 거래 내역 조회",
				() -> requestTransactions(userKey, cardNo, cvc, startDate, endDate));
	}

	private List<FinanceCardTransaction> requestTransactions(
			String userKey,
			String cardNo,
			String cvc,
			LocalDate startDate,
			LocalDate endDate
	) {
		FinanceCardTransactionRequest request = new FinanceCardTransactionRequest(
				headerFactory.create(API_NAME, userKey),
				cardNo,
				cvc,
				DATE_FORMAT.format(startDate),
				DATE_FORMAT.format(endDate)
		);
		return financeRestClient.post()
				.uri(TRANSACTION_LIST_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(response));
	}

	private List<FinanceCardTransaction> parseResponse(
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

		FinanceCardTransactionResponse transactionResponse =
				FinanceHttpSupport.convert(objectMapper, root, FinanceCardTransactionResponse.class);
		FinanceCardTransactionRecord record = transactionResponse.record();
		List<FinanceCardTransaction> transactions = record == null
				? List.of()
				: record.transactionsOrEmpty();
		transactions.forEach(this::validateTransaction);
		return transactions;
	}

	private void validateTransaction(FinanceCardTransaction transaction) {
		if (isBlank(transaction.transactionUniqueNo())
				|| isBlank(transaction.transactionDate())
				|| isBlank(transaction.transactionTime())
				|| transaction.transactionBalance() == null
				|| isBlank(transaction.cardStatus())) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
	}

	private static void validateRequest(
			String userKey,
			String cardNo,
			String cvc,
			LocalDate startDate,
			LocalDate endDate
	) {
		FinanceAccountTransactionRestClient.requireText(userKey, "금융망 사용자 키");
		FinanceAccountTransactionRestClient.requireText(cardNo, "카드번호");
		if (cvc == null || cvc.length() != CVC_LENGTH) {
			throw new IllegalArgumentException("CVC는 3자리여야 합니다.");
		}
		FinanceAccountTransactionRestClient.validatePeriod(startDate, endDate);
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
