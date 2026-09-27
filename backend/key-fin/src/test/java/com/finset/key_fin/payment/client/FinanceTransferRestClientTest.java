package com.finset.key_fin.payment.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

import java.net.URI;
import java.time.Duration;
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
import com.finset.key_fin.payment.dto.response.FinanceTransferResult;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult.Status;
import tools.jackson.databind.json.JsonMapper;

class FinanceTransferRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String TRANSFER_URL = BASE_URL + "/edu/demandDeposit/updateDemandDepositAccountTransfer";
	private static final String USER_KEY = "test-user-key";
	private static final String TX_NO = "20260915083000123456";
	private static final String FROM = "0019860000000001";
	private static final String TO = "0019860000000002";
	private static final String SUCCESS_HEADER = """
			"Header": {"responseCode": "H0000", "responseMessage": "정상처리 되었습니다."}
			""";

	private MockRestServiceServer server;
	private FinanceTransferRestClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
		server = MockRestServiceServer.bindTo(builder).build();
		FinanceProperties properties = new FinanceProperties(
				URI.create(BASE_URL), "test-api-key",
				Duration.ofSeconds(3), Duration.ofSeconds(5), 3, Duration.ZERO, Duration.ZERO, Duration.ofSeconds(1));
		client = new FinanceTransferRestClient(
				builder.build(), new FinanceHeaderFactory(properties), new FinanceRetryExecutor(properties),
				JsonMapper.builder().build());
	}

	@Test
	@DisplayName("지정한 기관거래고유번호로 출금→입금 이체를 요청하고 H0000이면 EXECUTED")
	void transfersWithGivenTransactionNo() {
		server.expect(requestTo(TRANSFER_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(jsonPath("$.Header.apiName").value("updateDemandDepositAccountTransfer"))
				.andExpect(jsonPath("$.Header.institutionTransactionUniqueNo").value(TX_NO))
				.andExpect(jsonPath("$.Header.userKey").value(USER_KEY))
				.andExpect(jsonPath("$.withdrawalAccountNo").value(FROM))
				.andExpect(jsonPath("$.depositAccountNo").value(TO))
				.andExpect(jsonPath("$.transactionBalance").value("230000"))
				.andExpect(jsonPath("$.depositTransactionSummary").value("KeyFin 결제 준비 - 월세"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [{"transactionUniqueNo": "501", "accountNo": "0019860000000001", "transactionDate": "20260915",
								           "transactionType": "2", "transactionTypeName": "출금이체", "transactionAccountNo": "0019860000000002"}]}
								"""));

		FinanceTransferResult result = client.transfer(USER_KEY, TX_NO, FROM, TO, 230000L, "KeyFin 결제 준비 - 월세");

		assertThat(result.status()).isEqualTo(Status.EXECUTED);
		assertThat(result.isSuccess()).isTrue();
		server.verify();
	}

	@Test
	@DisplayName("일시 장애(503) 뒤 재시도는 같은 기관거래고유번호로 나가고, H1007이면 이미 처리된 것으로 본다")
	void retriesWithSameTransactionNoAndTreatsDuplicateAsProcessed() {
		server.expect(requestTo(TRANSFER_URL))
				.andExpect(jsonPath("$.Header.institutionTransactionUniqueNo").value(TX_NO))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));
		server.expect(requestTo(TRANSFER_URL))
				.andExpect(jsonPath("$.Header.institutionTransactionUniqueNo").value(TX_NO))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"Header\": {\"responseCode\": \"H1007\", \"responseMessage\": \"기관거래고유번호가 중복된 값입니다.\"}}"));

		FinanceTransferResult result = client.transfer(USER_KEY, TX_NO, FROM, TO, 230000L, "KeyFin 결제 준비");

		assertThat(result.status()).isEqualTo(Status.ALREADY_PROCESSED);
		assertThat(result.isSuccess()).isTrue();
		server.verify();
	}

	@Test
	@DisplayName("잔액 부족(A1014)과 은행 한도(A1016/A1017)는 예외가 아니라 결과로 돌려준다")
	void returnsBusinessOutcomes() {
		server.expect(requestTo(TRANSFER_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"Header\": {\"responseCode\": \"A1014\", \"responseMessage\": \"계좌 잔액이 부족하여 거래가 실패했습니다.\"}}"));
		server.expect(requestTo(TRANSFER_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"Header\": {\"responseCode\": \"A1017\", \"responseMessage\": \"이체 가능 한도 초과(1일)\"}}"));

		FinanceTransferResult insufficient = client.transfer(USER_KEY, TX_NO, FROM, TO, 230000L, "s");
		FinanceTransferResult limit = client.transfer(USER_KEY, TX_NO, FROM, TO, 230000L, "s");

		assertThat(insufficient.status()).isEqualTo(Status.INSUFFICIENT_BALANCE);
		assertThat(insufficient.isSuccess()).isFalse();
		assertThat(limit.status()).isEqualTo(Status.BANK_LIMIT_EXCEEDED);
		assertThat(limit.responseCode()).isEqualTo("A1017");
		server.verify();
	}

	@Test
	@DisplayName("사용자 키가 무효하면 금융망 공통 오류로 매핑된다")
	void mapsFinanceError() {
		server.expect(requestTo(TRANSFER_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"Header\": {\"responseCode\": \"H1009\", \"responseMessage\": \"USER_KEY가 유효하지 않습니다.\"}}"));

		assertThatThrownBy(() -> client.transfer(USER_KEY, TX_NO, FROM, TO, 230000L, "s"))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(FinanceErrorCode.USER_KEY_INVALID);
	}

	@Test
	@DisplayName("금액이 0 이하이면 호출 전에 거부한다")
	void rejectsNonPositiveAmount() {
		assertThatThrownBy(() -> client.transfer(USER_KEY, TX_NO, FROM, TO, 0L, "s"))
				.isInstanceOf(IllegalArgumentException.class);
	}
}
