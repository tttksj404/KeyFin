package com.finset.key_fin.link.client;

import com.finset.key_fin.global.finance.client.FinanceResponseCode;
import com.finset.key_fin.global.finance.client.RetryableFinanceException;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.client.FinanceHttpSupport;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.link.dto.request.FinanceMemberSearchRequest;
import com.finset.key_fin.link.dto.response.FinanceMember;
import com.finset.key_fin.link.dto.response.FinanceMemberSearchResponse;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;

@Component
public class FinanceMemberRestClient implements FinanceMemberClient {

	private static final String MEMBER_SEARCH_PATH = "/member/search";
	private static final int MAX_USER_KEY_LENGTH = 60;

	private final RestClient financeRestClient;
	private final FinanceProperties properties;
	private final ObjectMapper objectMapper;
	private final FinanceRetryExecutor retryExecutor;

	public FinanceMemberRestClient(
			@Qualifier("financeRestClient")
			RestClient financeRestClient,
			FinanceProperties properties,
			ObjectMapper objectMapper,
			FinanceRetryExecutor retryExecutor
	) {
		this.financeRestClient = financeRestClient;
		this.properties = properties;
		this.objectMapper = objectMapper;
		this.retryExecutor = retryExecutor;
	}

	@Override
	public FinanceMember findByEmail(String email) {
		validateEmail(email);
		FinanceMemberSearchRequest request = new FinanceMemberSearchRequest(properties.apiKey(), email);
		return retryExecutor.execute("회원 조회", () -> requestMember(email, request));
	}

	private FinanceMember requestMember(String email, FinanceMemberSearchRequest request) {
		return financeRestClient.post()
				.uri(MEMBER_SEARCH_PATH)
				.contentType(MediaType.APPLICATION_JSON)
				.body(request)
				.exchange((httpRequest, response) -> parseResponse(email, response));
	}

	private FinanceMember parseResponse(
			String requestedEmail,
			RestClient.RequestHeadersSpec.ConvertibleClientHttpResponse response
	) throws IOException {
		HttpStatusCode statusCode = response.getStatusCode();
		String body = response.bodyTo(String.class);
		if (FinanceHttpSupport.isRetryableStatus(statusCode)) {
			throw FinanceHttpSupport.retryableResponse(response.getHeaders());
		}

		JsonNode root = FinanceHttpSupport.readTree(objectMapper, body);
		String upstreamErrorCode = findUpstreamErrorCode(root);
		if (!statusCode.is2xxSuccessful() || upstreamErrorCode != null) {
			throw mapUpstreamError(upstreamErrorCode);
		}

		FinanceMemberSearchResponse searchResponse =
				FinanceHttpSupport.convert(objectMapper, root, FinanceMemberSearchResponse.class);
		validateSuccessResponse(requestedEmail, searchResponse);
		return new FinanceMember(searchResponse.userId(), searchResponse.userKey());
	}

	private String findUpstreamErrorCode(JsonNode root) {
		String responseCode = FinanceHttpSupport.textOrNull(root.path("responseCode"));
		if (responseCode == null) {
			responseCode = FinanceHttpSupport.headerResponseCode(root);
		}
		if (responseCode == null || FinanceResponseCode.SUCCESS.matches(responseCode)) {
			return null;
		}
		return responseCode;
	}

	private RuntimeException mapUpstreamError(String responseCode) {
		if (FinanceResponseCode.MEMBER_NOT_FOUND.matches(responseCode)) {
			return new BusinessException(FinanceErrorCode.MEMBER_NOT_FOUND);
		}
		if (FinanceResponseCode.MEMBER_API_KEY_INVALID.matches(responseCode)) {
			return new BusinessException(FinanceErrorCode.CONFIGURATION_ERROR);
		}
		if (FinanceResponseCode.UNKNOWN_ERROR.matches(responseCode)) {
			return new RetryableFinanceException(null);
		}
		return new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
	}

	private void validateSuccessResponse(String requestedEmail, FinanceMemberSearchResponse response) {
		if (response == null
				|| !requestedEmail.equals(response.userId())
				|| response.userKey() == null
				|| response.userKey().isBlank()
				|| response.userKey().length() > MAX_USER_KEY_LENGTH) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
	}

	private void validateEmail(String email) {
		if (email == null || email.isBlank()) {
			throw new IllegalArgumentException("금융망 조회 이메일은 비어 있을 수 없습니다.");
		}
	}
}
