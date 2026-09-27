package com.finset.key_fin.transaction.client;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.client.FinanceHeaderErrors;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceHttpSupport;
import com.finset.key_fin.global.finance.client.FinanceResponseCode;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.transaction.dto.finance.request.FinanceAccountTransactionRequest;
import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransaction;
import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransactionRecord;
import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransactionResponse;
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
public class FinanceAccountTransactionRestClient implements FinanceAccountTransactionClient {

	static final String API_NAME = "inquireTransactionHistoryList";
	private static final String TRANSACTION_LIST_PATH = "/edu/demandDeposit/" + API_NAME;
	private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.BASIC_ISO_DATE;
	private static final String ALL_TRANSACTION_TYPES = "A";
	private static final String ASCENDING_ORDER = "ASC";

	private final RestClient financeRestClient;
	private final FinanceHeaderFactory headerFactory;
	private final FinanceRetryExecutor retryExecutor;
	private final ObjectMapper objectMapper;

	public FinanceAccountTransactionRestClient(
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
	public List<FinanceAccountTransaction> findTransactions(
			String userKey,
			String accountNo,
			LocalDate startDate,
			LocalDate endDate
	) {
		validateRequest(userKey, accountNo, startDate, endDate);
		return retryExecutor.execute("계좌 거래 내역 조회",
				() -> requestTransactions(userKey, accountNo, startDate, endDate));
	}

	private List<FinanceAccountTransaction> requestTransactions(
			String userKey,
			String accountNo,
			LocalDate startDate,
			LocalDate endDate
	) {
		FinanceAccountTransactionRequest request = new FinanceAccountTransactionRequest(
				headerFactory.create(API_NAME, userKey),
				accountNo,
				DATE_FORMAT.format(startDate),
				DATE_FORMAT.format(endDate),
				ALL_TRANSACTION_TYPES,
				ASCENDING_ORDER
		);
		return financeRestClient.post()
				.uri(TRANSACTION_LIST_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(response));
	}

	private List<FinanceAccountTransaction> parseResponse(
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

		FinanceAccountTransactionResponse transactionResponse =
				FinanceHttpSupport.convert(objectMapper, root, FinanceAccountTransactionResponse.class);
		FinanceAccountTransactionRecord record = transactionResponse.record();
		List<FinanceAccountTransaction> transactions = record == null
				? List.of()
				: record.transactionsOrEmpty();
		transactions.forEach(this::validateTransaction);
		return transactions;
	}

	private void validateTransaction(FinanceAccountTransaction transaction) {
		if (isBlank(transaction.transactionUniqueNo())
				|| isBlank(transaction.transactionDate())
				|| isBlank(transaction.transactionTime())
				|| isBlank(transaction.transactionType())
				|| isBlank(transaction.transactionTypeName())
				|| transaction.transactionBalance() == null
				|| transaction.transactionAfterBalance() == null) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
	}

	private static void validateRequest(
			String userKey,
			String accountNo,
			LocalDate startDate,
			LocalDate endDate
	) {
		requireText(userKey, "금융망 사용자 키");
		requireText(accountNo, "계좌번호");
		validatePeriod(startDate, endDate);
	}

	static void validatePeriod(LocalDate startDate, LocalDate endDate) {
		if (startDate == null || endDate == null || startDate.isAfter(endDate)) {
			throw new IllegalArgumentException("거래 조회 기간이 올바르지 않습니다.");
		}
	}

	static void requireText(String value, String name) {
		if (isBlank(value)) {
			throw new IllegalArgumentException(name + "는 비어 있을 수 없습니다.");
		}
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
