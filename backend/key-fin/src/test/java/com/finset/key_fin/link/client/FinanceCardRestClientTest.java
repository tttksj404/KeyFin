package com.finset.key_fin.link.client;

import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.link.dto.response.FinanceCard;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.ExpectedCount;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.json.JsonMapper;

import java.net.URI;
import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

class FinanceCardRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String CARD_LIST_URL = BASE_URL + "/edu/creditCard/inquireSignUpCreditCardList";
	private static final String API_KEY = "test-api-key";
	private static final String USER_KEY = "test-user-key";
	private static final String SUCCESS_HEADER = """
			"Header": {"responseCode": "H0000", "responseMessage": "정상처리 되었습니다."}
			""";

	private MockRestServiceServer server;
	private FinanceCardRestClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
		server = MockRestServiceServer.bindTo(builder).build();
		FinanceProperties properties = new FinanceProperties(
				URI.create(BASE_URL),
				API_KEY,
				Duration.ofSeconds(3),
				Duration.ofSeconds(5),
				3,
				Duration.ZERO,
				Duration.ZERO,
				Duration.ofSeconds(1)
		);
		client = new FinanceCardRestClient(
				builder.build(),
				new FinanceHeaderFactory(properties),
				new FinanceRetryExecutor(properties),
				JsonMapper.builder().build()
		);
	}

	@Test
	void 공통_Header를_담아_카드_목록을_조회한다() {
		server.expect(requestTo(CARD_LIST_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(content().contentType(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.Header.apiName").value("inquireSignUpCreditCardList"))
				.andExpect(jsonPath("$.Header.apiServiceCode").value("inquireSignUpCreditCardList"))
				.andExpect(jsonPath("$.Header.apiKey").value(API_KEY))
				.andExpect(jsonPath("$.Header.userKey").value(USER_KEY))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [
								  {
								    "cardNo": "1003198565339181", "cvc": "149", "cardUniqueNo": "1003-a139e9f23f1a4cc",
								    "cardIssuerCode": "1003", "cardIssuerName": "롯데카드", "cardName": "디지로카 SEOUL",
								    "baselinePerformance": "0", "maxBenefitLimit": "200000", "cardDescription": "생활 20%할인",
								    "cardExpiryDate": "20290409", "withdrawalAccountNo": "0323555042323510", "withdrawalDate": "4"
								  },
								  {
								    "cardNo": "1005518816096479", "cvc": "725", "cardIssuerCode": "1005",
								    "cardIssuerName": "신한카드", "cardName": "신한 TRAVEL 카드",
								    "withdrawalAccountNo": "0323555042323510", "withdrawalDate": "1"
								  }
								]}
								"""));

		List<FinanceCard> cards = client.findCards(USER_KEY);

		assertThat(cards).hasSize(2);
		FinanceCard first = cards.get(0);
		assertThat(first.cardNo()).isEqualTo("1003198565339181");
		assertThat(first.cvc()).isEqualTo("149");
		assertThat(first.cardIssuerCode()).isEqualTo("1003");
		assertThat(first.cardIssuerName()).isEqualTo("롯데카드");
		assertThat(first.cardName()).isEqualTo("디지로카 SEOUL");
		assertThat(first.withdrawalAccountNo()).isEqualTo("0323555042323510");
		server.verify();
	}

	@Test
	void 카드가_없어_REC가_없으면_빈_목록을_반환한다() {
		server.expect(requestTo(CARD_LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + "}"));

		assertThat(client.findCards(USER_KEY)).isEmpty();
		server.verify();
	}

	@Test
	void 사용자_키가_무효하면_재연결_필요_오류를_반환한다() {
		server.expect(ExpectedCount.once(), requestTo(CARD_LIST_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header": {"responseCode": "H1009", "responseMessage": "USER_KEY가 유효하지 않습니다."}}
								"""));

		assertFinanceError(FinanceErrorCode.USER_KEY_INVALID, () -> client.findCards(USER_KEY));
		server.verify();
	}

	@Test
	void 금융망_서버_오류는_최대_시도_후_서비스_이용_불가로_변환한다() {
		server.expect(ExpectedCount.times(3), requestTo(CARD_LIST_URL))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

		assertFinanceError(FinanceErrorCode.SERVICE_UNAVAILABLE, () -> client.findCards(USER_KEY));
		server.verify();
	}

	@Test
	void CVC가_3자리가_아니면_잘못된_응답으로_처리한다() {
		server.expect(requestTo(CARD_LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [{"cardNo": "1003198565339181", "cvc": "14", "cardIssuerCode": "1003",
								           "cardIssuerName": "롯데카드", "cardName": "디지로카 SEOUL", "withdrawalDate": "4"}]}
								"""));

		assertFinanceError(FinanceErrorCode.INVALID_RESPONSE, () -> client.findCards(USER_KEY));
	}

	@Test
	void 출금_요일이_1에서_7이_아니면_잘못된_응답으로_처리한다() {
		server.expect(requestTo(CARD_LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [{"cardNo": "1003198565339181", "cvc": "143", "cardIssuerCode": "1003",
								           "cardIssuerName": "롯데카드", "cardName": "디지로카 SEOUL", "withdrawalDate": "8"}]}
								"""));

		assertFinanceError(FinanceErrorCode.INVALID_RESPONSE, () -> client.findCards(USER_KEY));
	}

	@Test
	void 카드번호와_CVC는_toString에_노출하지_않는다() {
		FinanceCard card = new FinanceCard(
				"1003198565339181", "149", "1003-a139e9f23f1a4cc", "1003", "롯데카드",
				"디지로카 SEOUL", "20290409", "0323555042323510", "4"
		);

		assertThat(card.toString())
				.doesNotContain("1003198565339181")
				.doesNotContain("149")
				.contains("cardNo=****9181")
				.contains("cvc=***");
	}

	@Test
	void 사용자_키는_비어_있을_수_없다() {
		assertThatIllegalArgumentException().isThrownBy(() -> client.findCards(" "));
	}

	private void assertFinanceError(FinanceErrorCode expected, Runnable action) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(expected);
	}
}
