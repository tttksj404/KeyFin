package com.finset.key_fin.transaction.client;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransaction;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.json.JsonMapper;

import java.net.URI;
import java.time.Duration;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

class FinanceAccountTransactionRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String TRANSACTION_URL = BASE_URL
			+ "/edu/demandDeposit/inquireTransactionHistoryList";
	private static final String API_KEY = "test-api-key";
	private static final String USER_KEY = "test-user-key";
	private static final LocalDate START_DATE = LocalDate.of(2026, 9, 1);
	private static final LocalDate END_DATE = LocalDate.of(2026, 9, 14);

	private MockRestServiceServer server;
	private FinanceAccountTransactionRestClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
		server = MockRestServiceServer.bindTo(builder).build();
		FinanceProperties properties = properties();
		client = new FinanceAccountTransactionRestClient(
				builder.build(),
				new FinanceHeaderFactory(properties),
				new FinanceRetryExecutor(properties),
				JsonMapper.builder().build()
		);
	}

	@Test
	void 전체_계좌_거래를_오름차순으로_조회한다() {
		server.expect(requestTo(TRANSACTION_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(content().contentType(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.Header.apiName").value("inquireTransactionHistoryList"))
				.andExpect(jsonPath("$.Header.apiKey").value(API_KEY))
				.andExpect(jsonPath("$.Header.userKey").value(USER_KEY))
				.andExpect(jsonPath("$.accountNo").value("0016174648358792"))
				.andExpect(jsonPath("$.startDate").value("20260901"))
				.andExpect(jsonPath("$.endDate").value("20260914"))
				.andExpect(jsonPath("$.transactionType").value("A"))
				.andExpect(jsonPath("$.orderByType").value("ASC"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header":{"responseCode":"H0000","responseMessage":"정상처리 되었습니다."},
								 "REC":{"totalCount":"1","list":[{
								   "transactionUniqueNo":"61","transactionDate":"20260914","transactionTime":"103229",
								   "transactionType":"2","transactionTypeName":"출금(이체)",
								   "transactionAccountNo":"0204667768182760","transactionBalance":"10000",
								   "transactionAfterBalance":"990000","transactionSummary":"계좌 이체","transactionMemo":""
								 }]}}
								"""));

		List<FinanceAccountTransaction> transactions = client.findTransactions(
				USER_KEY, "0016174648358792", START_DATE, END_DATE
		);

		assertThat(transactions).hasSize(1);
		assertThat(transactions.getFirst())
				.extracting("transactionUniqueNo", "transactionTypeName", "transactionAccountNo",
						"transactionBalance", "transactionAfterBalance")
				.containsExactly("61", "출금(이체)", "0204667768182760", 10_000L, 990_000L);
		server.verify();
	}

	@Test
	void 거래_목록이_없으면_빈_목록을_반환한다() {
		server.expect(requestTo(TRANSACTION_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header":{"responseCode":"H0000"},"REC":{"totalCount":"0","list":[]}}
								"""));

		assertThat(client.findTransactions(USER_KEY, "0016174648358792", START_DATE, END_DATE)).isEmpty();
		server.verify();
	}

	@Test
	void 금융망_오류를_내부_오류로_변환한다() {
		server.expect(requestTo(TRANSACTION_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header":{"responseCode":"H1009","responseMessage":"USER_KEY가 유효하지 않습니다."}}
								"""));

		assertThatThrownBy(() -> client.findTransactions(
				USER_KEY, "0016174648358792", START_DATE, END_DATE
		)).isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(FinanceErrorCode.USER_KEY_INVALID);
		server.verify();
	}

	@Test
	void 조회_시작일이_종료일보다_늦으면_거절한다() {
		assertThatIllegalArgumentException().isThrownBy(() -> client.findTransactions(
				USER_KEY, "0016174648358792", END_DATE, START_DATE
		));
	}

	private FinanceProperties properties() {
		return new FinanceProperties(
				URI.create(BASE_URL), API_KEY,
				Duration.ofSeconds(3), Duration.ofSeconds(5), 1,
				Duration.ZERO, Duration.ZERO, Duration.ofSeconds(1)
		);
	}
}
