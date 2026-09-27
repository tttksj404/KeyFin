package com.finset.key_fin.link;

import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.ExpectedCount;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class FinanceLinkIntegrationTest extends SpringIntegrationTestSupport {

	private static final String MEMBER_SEARCH_URL = FINANCE_BASE_URL + "/member/search";
	private static final String ACCOUNT_LIST_URL = FINANCE_BASE_URL + "/edu/demandDeposit/inquireDemandDepositAccountList";
	private static final String CARD_LIST_URL = FINANCE_BASE_URL + "/edu/creditCard/inquireSignUpCreditCardList";
	private static final String FINANCE_EMAIL = "finance@keyfin.test";
	private static final String KB_ACCOUNT_NO = "0041456503815897";
	private static final String SHINHAN_ACCOUNT_NO = "0880680068408149";
	private static final String SHINHAN_CARD_NO = "1005872701650761";
	private static final AtomicInteger EMAIL_SEQUENCE = new AtomicInteger();

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private MockRestServiceServer financeServer;

	private String accessToken;
	private String finUserKey;

	@BeforeEach
	void setUp() throws Exception {
		financeServer.reset();
		int sequence = EMAIL_SEQUENCE.incrementAndGet();
		String email = "user" + sequence + "@keyfin.test";
		finUserKey = "00000000-0000-0000-0000-%012d".formatted(sequence);
		mockMvc.perform(post("/api/v1/auth/signup")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"email\":\"" + email + "\",\"password\":\"P@ssw0rd!\",\"name\":\"통합테스트\"}"))
				.andExpect(status().isCreated());
		MvcResult login = mockMvc.perform(post("/api/v1/auth/login")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"email\":\"" + email + "\",\"password\":\"P@ssw0rd!\"}"))
				.andExpect(status().isOk())
				.andReturn();
		accessToken = JsonPath.read(login.getResponse().getContentAsString(), "$.data.accessToken");
	}

	@AfterEach
	void tearDown() {
		financeServer.verify();
	}

	@Test
	void 회원_연결부터_계좌_카드_선택_연결과_해제까지_한_흐름으로_동작한다() throws Exception {
		mockMvc.perform(authed(get("/api/v1/links/status")))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.connected", false));

		mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isConflict())
				.andExpect(jsonPathValue("$.code", "LINK_002"));

		expectMemberSearchSuccess();
		mockMvc.perform(authed(post("/api/v1/links/connect"))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"financeEmail\":\"" + FINANCE_EMAIL + "\"}"))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.connected", true));

		expectAccountAndCardLists();
		MvcResult candidates = mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.accounts.length()", 2))
				.andExpect(jsonPathValue("$.data.accounts[0].finAccountNo", KB_ACCOUNT_NO))
				.andExpect(jsonPathValue("$.data.accounts[0].managed", false))
				.andExpect(jsonPathValue("$.data.accounts[1].managed", false))
				.andExpect(jsonPathValue("$.data.cards[0].cardNo", SHINHAN_CARD_NO))
				.andExpect(jsonPathValue("$.data.cards[0].managed", false))
				.andReturn();
		String body = candidates.getResponse().getContentAsString();
		Number kbAccountId = JsonPath.read(body, "$.data.accounts[0].id");
		Number shinhanAccountId = JsonPath.read(body, "$.data.accounts[1].id");
		Number cardId = JsonPath.read(body, "$.data.cards[0].id");
		assertThat(kbAccountId).isNotNull();
		assertThat(shinhanAccountId).isNotNull();
		assertThat(cardId).isNotNull();

		resetFinanceServer();
		mockMvc.perform(authed(post("/api/v1/links"))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"accountIds\":[" + kbAccountId + "," + shinhanAccountId + "],\"cardIds\":[" + cardId + "]}"))
				.andExpect(status().isCreated())
				.andExpect(jsonPathValue("$.data.accounts", 2))
				.andExpect(jsonPathValue("$.data.cards", 1));

		mockMvc.perform(authed(post("/api/v1/links"))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"accountIds\":[" + kbAccountId + "],\"cardIds\":[" + cardId + "]}"))
				.andExpect(status().isCreated())
				.andExpect(jsonPathValue("$.data.accounts", 0))
				.andExpect(jsonPathValue("$.data.cards", 0));

		expectAccountAndCardLists();
		mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.accounts[0].id", kbAccountId.intValue()))
				.andExpect(jsonPathValue("$.data.accounts[0].managed", true))
				.andExpect(jsonPathValue("$.data.accounts[1].managed", true))
				.andExpect(jsonPathValue("$.data.cards[0].id", cardId.intValue()))
				.andExpect(jsonPathValue("$.data.cards[0].managed", true));

		resetFinanceServer();
		mockMvc.perform(authed(delete("/api/v1/links/cards/" + cardId)))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.success", true));

		expectAccountAndCardLists();
		mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.accounts[0].managed", true))
				.andExpect(jsonPathValue("$.data.cards[0].id", cardId.intValue()))
				.andExpect(jsonPathValue("$.data.cards[0].managed", false));

		resetFinanceServer();
		mockMvc.perform(authed(post("/api/v1/links"))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"cardIds\":[" + cardId + "]}"))
				.andExpect(status().isCreated())
				.andExpect(jsonPathValue("$.data.cards", 1));

		expectAccountAndCardLists();
		mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.cards[0].id", cardId.intValue()))
				.andExpect(jsonPathValue("$.data.cards[0].managed", true));
	}

	@Test
	void 금융망에_없는_회원은_연결할_수_없다() throws Exception {
		financeServer.expect(ExpectedCount.once(), requestTo(MEMBER_SEARCH_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"responseCode\":\"E4003\",\"responseMessage\":\"존재하지 않는 ID입니다.\"}"));

		mockMvc.perform(authed(post("/api/v1/links/connect"))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"financeEmail\":\"nobody@keyfin.test\"}"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPathValue("$.code", "FINANCE_001"));

		mockMvc.perform(authed(get("/api/v1/links/status")))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.connected", false));
	}

	@Test
	void 본인_소유가_아닌_계좌_ID는_연결할_수_없다() throws Exception {
		mockMvc.perform(authed(post("/api/v1/links"))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"accountIds\":[999999]}"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPathValue("$.code", "LINK_004"));
	}

	@Test
	void 후보_목록_조회만_해도_자산이_미선택_상태로_저장된다() throws Exception {
		connectFinance();
		expectAccountAndCardLists();
		mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isOk());

		expectAccountAndCardLists();
		MvcResult again = mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isOk())
				.andExpect(jsonPathValue("$.data.accounts.length()", 2))
				.andExpect(jsonPathValue("$.data.accounts[0].managed", false))
				.andExpect(jsonPathValue("$.data.cards[0].managed", false))
				.andReturn();
		Number firstId = JsonPath.read(again.getResponse().getContentAsString(), "$.data.accounts[0].id");
		assertThat(firstId).isNotNull();
	}

	@Test
	void 다른_사용자의_카드는_해제할_수_없다() throws Exception {
		mockMvc.perform(authed(delete("/api/v1/links/cards/999999")))
				.andExpect(status().isNotFound())
				.andExpect(jsonPathValue("$.code", "LINK_005"));
	}

	@Test
	void 인증_없는_요청은_거절한다() throws Exception {
		mockMvc.perform(get("/api/v1/links/candidates"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPathValue("$.code", "AUTH_005"));
	}

	@Test
	void 금융망_장애가_계속되면_재시도_후_503으로_응답한다() throws Exception {
		connectFinance();
		resetFinanceServer();
		financeServer.expect(ExpectedCount.times(3), requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

		mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isServiceUnavailable())
				.andExpect(jsonPathValue("$.code", "FINANCE_004"));
	}

	@Test
	void 금융망_사용자_키가_무효하면_재연결_필요로_응답한다() throws Exception {
		connectFinance();
		resetFinanceServer();
		financeServer.expect(ExpectedCount.once(), requestTo(ACCOUNT_LIST_URL))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"responseCode\":\"H1009\",\"responseMessage\":\"USER_KEY가 유효하지 않습니다.\"}"));

		mockMvc.perform(authed(get("/api/v1/links/candidates")))
				.andExpect(status().isConflict())
				.andExpect(jsonPathValue("$.code", "FINANCE_005"));
	}

	private void connectFinance() throws Exception {
		expectMemberSearchSuccess();
		mockMvc.perform(authed(post("/api/v1/links/connect"))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"financeEmail\":\"" + FINANCE_EMAIL + "\"}"))
				.andExpect(status().isOk());
	}

	private void expectMemberSearchSuccess() {
		resetFinanceServer();
		financeServer.expect(ExpectedCount.once(), requestTo(MEMBER_SEARCH_URL))
				.andExpect(jsonPath("$.apiKey").value(FINANCE_API_KEY))
				.andExpect(jsonPath("$.userId").value(FINANCE_EMAIL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("{\"userId\":\"" + FINANCE_EMAIL + "\",\"userName\":\"finance\",\"institutionCode\":\"00100\","
								+ "\"userKey\":\"" + finUserKey + "\",\"created\":\"20260910\",\"modified\":\"20260910\"}"));
	}

	private void expectAccountAndCardLists() {
		resetFinanceServer();
		financeServer.expect(ExpectedCount.once(), requestTo(ACCOUNT_LIST_URL))
				.andExpect(jsonPath("$.Header.apiName").value("inquireDemandDepositAccountList"))
				.andExpect(jsonPath("$.Header.apiKey").value(FINANCE_API_KEY))
				.andExpect(jsonPath("$.Header.userKey").value(finUserKey))
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.APPLICATION_JSON).body(accountListBody()));
		expectCardList();
	}

	private void resetFinanceServer() {
		financeServer.verify();
		financeServer.reset();
	}

	private void expectCardList() {
		financeServer.expect(ExpectedCount.once(), requestTo(CARD_LIST_URL))
				.andExpect(jsonPath("$.Header.apiName").value("inquireSignUpCreditCardList"))
				.andExpect(jsonPath("$.Header.userKey").value(finUserKey))
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.APPLICATION_JSON).body("""
						{"Header":{"responseCode":"H0000","responseMessage":"정상처리 되었습니다."},
						 "REC":[{"cardNo":"%s","cvc":"725","cardUniqueNo":"1005-x","cardIssuerCode":"1005",
						         "cardIssuerName":"신한카드","cardName":"신한 딥디저트 카드","cardExpiryDate":"20310910",
						         "withdrawalAccountNo":"%s","withdrawalDate":"1"}]}
						""".formatted(SHINHAN_CARD_NO, SHINHAN_ACCOUNT_NO)));
	}

	private String accountListBody() {
		return """
				{"Header":{"responseCode":"H0000","responseMessage":"정상처리 되었습니다."},
				 "REC":[
				   {"bankCode":"004","bankName":"국민은행","accountNo":"%s","accountName":"국민 수시입출금",
				    "accountTypeCode":"1","accountBalance":"3000000","currency":"KRW"},
				   {"bankCode":"088","bankName":"신한은행","accountNo":"%s","accountName":"신한 수시입출금",
				    "accountTypeCode":"1","accountBalance":"125000","currency":"KRW"},
				   {"bankCode":"020","bankName":"우리은행","accountNo":"0204667768182760","accountName":"우리 정기예금",
				    "accountTypeCode":"2","accountBalance":"8003477","currency":"KRW"}
				 ]}
				""".formatted(KB_ACCOUNT_NO, SHINHAN_ACCOUNT_NO);
	}

	private MockHttpServletRequestBuilder authed(MockHttpServletRequestBuilder builder) {
		return builder.header("Authorization", "Bearer " + accessToken);
	}

	private static org.springframework.test.web.servlet.ResultMatcher jsonPathValue(String expression, Object expected) {
		return org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath(expression).value(expected);
	}
}
