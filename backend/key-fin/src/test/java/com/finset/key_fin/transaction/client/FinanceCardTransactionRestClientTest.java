package com.finset.key_fin.transaction.client;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransaction;
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

class FinanceCardTransactionRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String TRANSACTION_URL = BASE_URL
			+ "/edu/creditCard/inquireCreditCardTransactionList";
	private static final String API_KEY = "test-api-key";
	private static final String USER_KEY = "test-user-key";
	private static final LocalDate START_DATE = LocalDate.of(2026, 9, 1);
	private static final LocalDate END_DATE = LocalDate.of(2026, 9, 14);

	private MockRestServiceServer server;
	private FinanceCardTransactionRestClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
		server = MockRestServiceServer.bindTo(builder).build();
		FinanceProperties properties = properties();
		client = new FinanceCardTransactionRestClient(
				builder.build(),
				new FinanceHeaderFactory(properties),
				new FinanceRetryExecutor(properties),
				JsonMapper.builder().build()
		);
	}

	@Test
	void 카드_거래_내역을_조회한다() {
		server.expect(requestTo(TRANSACTION_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(content().contentType(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.Header.apiName").value("inquireCreditCardTransactionList"))
				.andExpect(jsonPath("$.Header.apiKey").value(API_KEY))
				.andExpect(jsonPath("$.Header.userKey").value(USER_KEY))
				.andExpect(jsonPath("$.cardNo").value("1005518816096479"))
				.andExpect(jsonPath("$.cvc").value("725"))
				.andExpect(jsonPath("$.startDate").value("20260901"))
				.andExpect(jsonPath("$.endDate").value("20260914"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header":{"responseCode":"H0000","responseMessage":"정상처리 되었습니다."},
								 "REC":{"cardIssuerCode":"1005","cardIssuerName":"신한카드","cardName":"신한 TRAVEL 카드",
								 "cardNo":"1005518816096479","estimatedBalance":"2000000","transactionList":[{
								   "transactionUniqueNo":"20","categoryId":"CG-3fa85f6425e811e","categoryName":"주유",
								   "merchantId":"40114","merchantName":"현대오일뱅크","transactionDate":"20260914",
								   "transactionTime":"094431","transactionBalance":"1000000","cardStatus":"승인",
								   "billStatementsYn":"N","billStatementsStatus":"미결제"
								 }]}}
								"""));

		List<FinanceCardTransaction> transactions = client.findTransactions(
				USER_KEY, "1005518816096479", "725", START_DATE, END_DATE
		);

		assertThat(transactions).hasSize(1);
		assertThat(transactions.getFirst())
				.extracting("transactionUniqueNo", "merchantId", "merchantName", "transactionBalance", "cardStatus")
				.containsExactly("20", 40_114L, "현대오일뱅크", 1_000_000L, "승인");
		server.verify();
	}

	@Test
	void 카드_거래가_없으면_빈_목록을_반환한다() {
		server.expect(requestTo(TRANSACTION_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header":{"responseCode":"H0000"},
								 "REC":{"cardNo":"1005518816096479","estimatedBalance":"0","transactionList":[]}}
								"""));

		assertThat(client.findTransactions(
				USER_KEY, "1005518816096479", "725", START_DATE, END_DATE
		)).isEmpty();
		server.verify();
	}

	@Test
	void 필수_응답값이_없으면_잘못된_응답으로_처리한다() {
		server.expect(requestTo(TRANSACTION_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header":{"responseCode":"H0000"},"REC":{"transactionList":[{
								 "transactionUniqueNo":"20","transactionDate":"20260914","transactionTime":"094431"
								}]}}
								"""));

		assertThatThrownBy(() -> client.findTransactions(
				USER_KEY, "1005518816096479", "725", START_DATE, END_DATE
		)).isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(FinanceErrorCode.INVALID_RESPONSE);
		server.verify();
	}

	@Test
	void CVC가_세_자리가_아니면_거절한다() {
		assertThatIllegalArgumentException().isThrownBy(() -> client.findTransactions(
				USER_KEY, "1005518816096479", "72", START_DATE, END_DATE
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
