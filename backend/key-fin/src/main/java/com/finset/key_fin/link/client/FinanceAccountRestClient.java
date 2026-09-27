package com.finset.key_fin.link.client;

import com.finset.key_fin.global.finance.client.FinanceResponseCode;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.client.FinanceHttpSupport;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceHeaderErrors;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.dto.request.FinanceHeaderRequest;
import com.finset.key_fin.link.dto.response.FinanceAccount;
import com.finset.key_fin.link.dto.response.FinanceAccountListResponse;
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
public class FinanceAccountRestClient implements FinanceAccountClient {

	static final String API_NAME = "inquireDemandDepositAccountList";
	private static final String ACCOUNT_LIST_PATH = "/edu/demandDeposit/" + API_NAME;

	private final RestClient financeRestClient;
	private final FinanceHeaderFactory headerFactory;
	private final FinanceRetryExecutor retryExecutor;
	private final ObjectMapper objectMapper;

	public FinanceAccountRestClient(
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
	public List<FinanceAccount> findAccounts(String userKey) {
		if (userKey == null || userKey.isBlank()) {
			throw new IllegalArgumentException("금융망 사용자 키는 비어 있을 수 없습니다.");
		}
		return retryExecutor.execute("계좌 목록 조회", () -> requestAccounts(userKey));
	}

	private List<FinanceAccount> requestAccounts(String userKey) {
		FinanceHeaderRequest request = new FinanceHeaderRequest(headerFactory.create(API_NAME, userKey));
		return financeRestClient.post()
				.uri(ACCOUNT_LIST_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(response));
	}

	private List<FinanceAccount> parseResponse(
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

		FinanceAccountListResponse listResponse =
				FinanceHttpSupport.convert(objectMapper, root, FinanceAccountListResponse.class);
		List<FinanceAccount> accounts = listResponse.accountsOrEmpty();
		accounts.forEach(this::validateAccount);
		return accounts;
	}

	private void validateAccount(FinanceAccount account) {
		if (account.accountNo() == null || account.accountNo().isBlank()
				|| account.bankCode() == null || account.bankCode().isBlank()
				|| account.bankName() == null || account.bankName().isBlank()
				|| account.accountBalance() == null) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
	}
}
