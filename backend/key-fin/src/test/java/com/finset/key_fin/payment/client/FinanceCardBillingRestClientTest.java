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
import java.time.LocalDateTime;
import java.time.YearMonth;
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
import com.finset.key_fin.payment.dto.response.FinanceBillingStatement;
import tools.jackson.databind.json.JsonMapper;

class FinanceCardBillingRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String STATEMENT_URL = BASE_URL + "/edu/creditCard/inquireBillingStatements";
	private static final String USER_KEY = "test-user-key";
	private static final String CARD_NO = "1001832868000001";
	private static final String CVC = "123";
	private static final String SUCCESS_HEADER = """
			"Header": {"responseCode": "H0000", "responseMessage": "정상처리 되었습니다."}
			""";

	private MockRestServiceServer server;
	private FinanceCardBillingRestClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
		server = MockRestServiceServer.bindTo(builder).build();
		FinanceProperties properties = new FinanceProperties(
				URI.create(BASE_URL), "test-api-key",
				Duration.ofSeconds(3), Duration.ofSeconds(5), 3, Duration.ZERO, Duration.ZERO, Duration.ofSeconds(1));
		client = new FinanceCardBillingRestClient(
				builder.build(), new FinanceHeaderFactory(properties), new FinanceRetryExecutor(properties),
				JsonMapper.builder().build());
	}

	@Test
	@DisplayName("월 단위로 조회하고, 응답의 월별 배열을 주차 청구서 목록으로 평탄화한다")
	void findsStatementsFlattened() {
		server.expect(requestTo(STATEMENT_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(jsonPath("$.Header.apiName").value("inquireBillingStatements"))
				.andExpect(jsonPath("$.Header.userKey").value(USER_KEY))
				.andExpect(jsonPath("$.cardNo").value(CARD_NO))
				.andExpect(jsonPath("$.cvc").value(CVC))
				.andExpect(jsonPath("$.startMonth").value("202608"))
				.andExpect(jsonPath("$.endMonth").value("202609"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [
								  {"billingMonth": "202608", "billingList": [
								    {"billingWeek": "5", "billingDate": "20260831", "totalBalance": "120000", "status": "결제완료", "paymentDate": "20260902", "paymentTime": "160000"}
								  ]},
								  {"billingMonth": "202609", "billingList": [
								    {"billingWeek": "2", "billingDate": "20260914", "totalBalance": "8900", "status": "미결제", "paymentDate": "", "paymentTime": ""}
								  ]}
								]}
								"""));

		List<FinanceBillingStatement> statements = client.findBillingStatements(
				USER_KEY, CARD_NO, CVC, YearMonth.of(2026, 8), YearMonth.of(2026, 9));

		assertThat(statements).hasSize(2);
		FinanceBillingStatement paid = statements.get(0);
		assertThat(paid.isPaid()).isTrue();
		assertThat(paid.amount()).isEqualTo(120000L);
		assertThat(paid.issuedOn()).isEqualTo(LocalDate.of(2026, 8, 31));
		assertThat(paid.paidAt()).isEqualTo(LocalDateTime.of(2026, 9, 2, 16, 0));
		FinanceBillingStatement unpaid = statements.get(1);
		assertThat(unpaid.isPaid()).isFalse();
		assertThat(unpaid.paidAt()).isNull();
		server.verify();
	}

	@Test
	@DisplayName("청구서가 없으면 빈 목록")
	void returnsEmptyWhenNoStatements() {
		server.expect(requestTo(STATEMENT_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + ", \"REC\": []}"));

		assertThat(client.findBillingStatements(USER_KEY, CARD_NO, CVC, YearMonth.of(2026, 9), YearMonth.of(2026, 9)))
				.isEmpty();
		server.verify();
	}

	@Test
	@DisplayName("사용자 키가 무효하면 금융망 공통 오류(USER_KEY_INVALID)로 매핑된다")
	void mapsFinanceError() {
		server.expect(requestTo(STATEMENT_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"Header\": {\"responseCode\": \"H1009\", \"responseMessage\": \"USER_KEY가 유효하지 않습니다.\"}}"));

		assertThatThrownBy(() -> client.findBillingStatements(
				USER_KEY, CARD_NO, CVC, YearMonth.of(2026, 9), YearMonth.of(2026, 9)))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(FinanceErrorCode.USER_KEY_INVALID);
		server.verify();
	}

	@Test
	@DisplayName("금액이 숫자가 아닌 청구서는 INVALID_RESPONSE")
	void rejectsMalformedStatement() {
		server.expect(requestTo(STATEMENT_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [{"billingMonth": "202609", "billingList": [
								  {"billingWeek": "2", "billingDate": "20260914", "totalBalance": "8,900", "status": "미결제"}]}]}
								"""));

		assertThatThrownBy(() -> client.findBillingStatements(
				USER_KEY, CARD_NO, CVC, YearMonth.of(2026, 9), YearMonth.of(2026, 9)))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(FinanceErrorCode.INVALID_RESPONSE);
	}
}
