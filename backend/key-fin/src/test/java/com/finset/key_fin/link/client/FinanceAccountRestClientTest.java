package com.finset.key_fin.link.client;

import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.link.dto.response.FinanceAccount;
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

class FinanceAccountRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String ACCOUNT_LIST_URL = BASE_URL + "/edu/demandDeposit/inquireDemandDepositAccountList";
	private static final String API_KEY = "test-api-key";
	private static final String USER_KEY = "test-user-key";
	private static final String SUCCESS_HEADER = """
			"Header": {"responseCode": "H0000", "responseMessage": "정상처리 되었습니다."}
			""";

	private MockRestServiceServer server;
	private FinanceAccountRestClient client;

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
		client = new FinanceAccountRestClient(
				builder.build(),
				new FinanceHeaderFactory(properties),
				new FinanceRetryExecutor(properties),
				JsonMapper.builder().build()
		);
	}

	@Test
	void 공통_Header를_담아_계좌_목록을_조회한다() {
		server.expect(requestTo(ACCOUNT_LIST_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(content().contentType(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.Header.apiName").value("inquireDemandDepositAccountList"))
				.andExpect(jsonPath("$.Header.apiServiceCode").value("inquireDemandDepositAccountList"))
				.andExpect(jsonPath("$.Header.institutionCode").value("00100"))
				.andExpect(jsonPath("$.Header.fintechAppNo").value("001"))
				.andExpect(jsonPath("$.Header.apiKey").value(API_KEY))
				.andExpect(jsonPath("$.Header.userKey").value(USER_KEY))
				.andExpect(jsonPath("$.Header.institutionTransactionUniqueNo").isString())
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [
								  {
								    "bankCode": "001", "bankName": "한국은행", "userName": "USER",
								    "accountNo": "0016174648358792", "accountName": "한국은행 수시입출금 상품명",
								    "accountTypeCode": "1", "accountTypeName": "수시입출금",
								    "accountCreatedDate": "20240401", "accountExpiryDate": "20290401",
								    "dailyTransferLimit": "100000000", "oneTimeTransferLimit": "20000000",
								    "accountBalance": "1500000", "lastTransactionDate": "", "currency": "KRW"
								  },
								  {
								    "bankCode": "020", "bankName": "우리은행", "accountNo": "0204667768182760",
								    "accountName": "우리은행 정기예금", "accountTypeCode": "2",
								    "accountBalance": "8003477", "currency": "KRW"
								  }
								]}
								"""));

		List<FinanceAccount> accounts = client.findAccounts(USER_KEY);

		assertThat(accounts).hasSize(2);
		FinanceAccount first = accounts.get(0);
		assertThat(first.bankCode()).isEqualTo("001");
		assertThat(first.bankName()).isEqualTo("한국은행");
		assertThat(first.accountNo()).isEqualTo("0016174648358792");
		assertThat(first.accountBalance()).isEqualTo(1_500_000L);
		assertThat(first.isDemandDeposit()).isTrue();
		assertThat(accounts.get(1).isDemandDeposit()).isFalse();
		server.verify();
	}

	@Test
	void 계좌가_없어_REC가_없으면_빈_목록을_반환한다() {
		server.expect(requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + "}"));

		assertThat(client.findAccounts(USER_KEY)).isEmpty();
		server.verify();
	}

	@Test
	void 사용자_키가_무효하면_재연결_필요_오류를_반환한다() {
		server.expect(ExpectedCount.once(), requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header": {"responseCode": "H1009", "responseMessage": "USER_KEY가 유효하지 않습니다."}}
								"""));

		assertFinanceError(FinanceErrorCode.USER_KEY_INVALID, () -> client.findAccounts(USER_KEY));
		server.verify();
	}

	@Test
	void API_Key가_무효하면_설정_오류를_반환한다() {
		server.expect(ExpectedCount.once(), requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header": {"responseCode": "H1008", "responseMessage": "API_KEY가 유효하지 않습니다."}}
								"""));

		assertFinanceError(FinanceErrorCode.CONFIGURATION_ERROR, () -> client.findAccounts(USER_KEY));
		server.verify();
	}

	@Test
	void Header_없이_최상위로_내려오는_오류_코드도_매핑한다() {
		server.expect(ExpectedCount.once(), requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"responseCode": "H1008", "responseMessage": "API_KEY가 유효하지 않습니다."}
								"""));

		assertFinanceError(FinanceErrorCode.CONFIGURATION_ERROR, () -> client.findAccounts(USER_KEY));
		server.verify();
	}

	@Test
	void 기관거래고유번호_중복_응답은_새_Header로_재시도한다() {
		server.expect(requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header": {"responseCode": "H1007", "responseMessage": "기관거래고유번호가 중복된 값입니다."}}
								"""));
		server.expect(requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [{"bankCode": "001", "bankName": "한국은행", "accountNo": "0016174648358792",
								           "accountTypeCode": "1", "accountBalance": "0", "currency": "KRW"}]}
								"""));

		assertThat(client.findAccounts(USER_KEY)).hasSize(1);
		server.verify();
	}

	@Test
	void 금융망_서버_오류는_최대_시도_후_서비스_이용_불가로_변환한다() {
		server.expect(ExpectedCount.times(3), requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

		assertFinanceError(FinanceErrorCode.SERVICE_UNAVAILABLE, () -> client.findAccounts(USER_KEY));
		server.verify();
	}

	@Test
	void 응답_Header가_없으면_잘못된_응답으로_처리한다() {
		server.expect(requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"REC": []}
								"""));

		assertFinanceError(FinanceErrorCode.INVALID_RESPONSE, () -> client.findAccounts(USER_KEY));
	}

	@Test
	void 계좌번호가_없는_항목은_잘못된_응답으로_처리한다() {
		server.expect(requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{" + SUCCESS_HEADER + """
								, "REC": [{"bankCode": "001", "bankName": "한국은행", "accountTypeCode": "1"}]}
								"""));

		assertFinanceError(FinanceErrorCode.INVALID_RESPONSE, () -> client.findAccounts(USER_KEY));
	}

	@Test
	void 사용자_키는_비어_있을_수_없다() {
		assertThatIllegalArgumentException().isThrownBy(() -> client.findAccounts(" "));
	}

	private void assertFinanceError(FinanceErrorCode expected, Runnable action) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(expected);
	}
}
