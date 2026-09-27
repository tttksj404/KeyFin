package com.finset.key_fin.payment.client;

import java.io.IOException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import com.finset.key_fin.global.finance.client.FinanceHeaderErrors;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceHttpSupport;
import com.finset.key_fin.global.finance.client.FinanceResponseCode;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.payment.dto.request.FinanceTransferRequest;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult.Status;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
public class FinanceTransferRestClient implements FinanceTransferClient {

	static final String API_NAME = "updateDemandDepositAccountTransfer";
	private static final String TRANSFER_PATH = "/edu/demandDeposit/" + API_NAME;

	private final RestClient financeRestClient;
	private final FinanceHeaderFactory headerFactory;
	private final FinanceRetryExecutor retryExecutor;
	private final ObjectMapper objectMapper;

	public FinanceTransferRestClient(
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
	public FinanceTransferResult transfer(
			String userKey, String transactionUniqueNo, String withdrawalAccountNo, String depositAccountNo,
			long amount, String summary) {
		if (isBlank(withdrawalAccountNo) || isBlank(depositAccountNo) || amount <= 0) {
			throw new IllegalArgumentException("출금·입금 계좌번호와 양수 금액이 필요합니다.");
		}
		// 재시도에도 같은 기관거래고유번호가 나가도록 요청 바디는 한 번만 만든다.
		FinanceTransferRequest request = new FinanceTransferRequest(
				headerFactory.create(API_NAME, userKey, transactionUniqueNo),
				depositAccountNo, String.valueOf(amount), withdrawalAccountNo, summary, summary);
		return retryExecutor.execute("계좌 이체", () -> financeRestClient.post()
				.uri(TRANSFER_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(response)));
	}

	private FinanceTransferResult parseResponse(
			RestClient.RequestHeadersSpec.ConvertibleClientHttpResponse response
	) throws IOException {
		HttpStatusCode statusCode = response.getStatusCode();
		String body = response.bodyTo(String.class);
		if (FinanceHttpSupport.isRetryableStatus(statusCode)) {
			throw FinanceHttpSupport.retryableResponse(response.getHeaders());
		}
		JsonNode root = FinanceHttpSupport.readTree(objectMapper, body);
		String responseCode = FinanceHttpSupport.headerResponseCode(root);
		if (FinanceResponseCode.SUCCESS.matches(responseCode)) {
			return FinanceTransferResult.EXECUTED;
		}
		if (FinanceResponseCode.HEADER_TRANSACTION_NO_DUPLICATED.matches(responseCode)) {
			return FinanceTransferResult.ALREADY_PROCESSED;
		}
		if (FinanceResponseCode.ACCOUNT_INSUFFICIENT_BALANCE.matches(responseCode)) {
			return new FinanceTransferResult(Status.INSUFFICIENT_BALANCE, responseCode);
		}
		if (FinanceResponseCode.TRANSFER_LIMIT_ONCE_EXCEEDED.matches(responseCode)
				|| FinanceResponseCode.TRANSFER_LIMIT_DAILY_EXCEEDED.matches(responseCode)) {
			return new FinanceTransferResult(Status.BANK_LIMIT_EXCEEDED, responseCode);
		}
		throw FinanceHeaderErrors.map(responseCode);
	}

	private static boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
