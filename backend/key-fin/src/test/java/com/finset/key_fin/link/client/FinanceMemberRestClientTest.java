package com.finset.key_fin.link.client;

import com.finset.key_fin.global.finance.client.FinanceRetryExecutor;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.link.dto.response.FinanceMember;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.client.ExpectedCount;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.json.JsonMapper;

import java.net.SocketTimeoutException;
import java.net.URI;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withException;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

class FinanceMemberRestClientTest {

	private static final String BASE_URL = "https://finance.example.com/finance/api/v1";
	private static final String API_KEY = "test-api-key";
	private static final String EMAIL = "qwer@qwer.com";
	private static final String USER_KEY = "test-user-key";

	private MockRestServiceServer server;
	private FinanceMemberRestClient client;

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
		client = new FinanceMemberRestClient(builder.build(), properties, JsonMapper.builder().build(), new FinanceRetryExecutor(properties));
	}

	@Test
	void 금융망_회원을_이메일로_조회한다() {
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andExpect(method(HttpMethod.POST))
				.andExpect(content().contentType(MediaType.APPLICATION_JSON))
				.andExpect(content().json("""
						{
						  "apiKey": "test-api-key",
						  "userId": "qwer@qwer.com"
						}
						"""))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{
								  "userId": "qwer@qwer.com",
								  "username": "테스트 사용자",
								  "institutionCode": "00100",
								  "userKey": "test-user-key",
								  "created": "20260910",
								  "modified": "20260910",
								  "ignoredField": "ignored"
								}
								"""));

		FinanceMember member = client.findByEmail(EMAIL);

		assertThat(member.userId()).isEqualTo(EMAIL);
		assertThat(member.userKey()).isEqualTo(USER_KEY);
		server.verify();
	}

	@Test
	void 금융망에_회원이_없으면_회원_없음_오류를_반환한다() {
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"responseCode":"E4003","responseMessage":"존재하지 않는 사용자입니다."}
								"""));

		assertFinanceError(FinanceErrorCode.MEMBER_NOT_FOUND, () -> client.findByEmail(EMAIL));
		server.verify();
	}

	@Test
	void API_Key가_잘못되면_설정_오류를_반환한다() {
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"Header":{"responseCode":"E4004","responseMessage":"API Key 오류"}}
								"""));

		assertFinanceError(FinanceErrorCode.CONFIGURATION_ERROR, () -> client.findByEmail(EMAIL));
		server.verify();
	}

	@Test
	void 금융망_서버_오류는_최대_시도_후_서비스_이용_불가로_변환한다() {
		server.expect(ExpectedCount.times(3), requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

		assertFinanceError(FinanceErrorCode.SERVICE_UNAVAILABLE, () -> client.findByEmail(EMAIL));
		server.verify();
	}

	@Test
	void 일시적인_서버_오류_후_금융망_회원_조회에_성공한다() {
		server.expect(ExpectedCount.times(2), requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"responseCode":"Q1000","responseMessage":"일시적인 오류"}
								"""));
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{
								  "userId": "qwer@qwer.com",
								  "userKey": "test-user-key"
								}
								"""));

		FinanceMember member = client.findByEmail(EMAIL);

		assertThat(member.userKey()).isEqualTo(USER_KEY);
		server.verify();
	}

	@Test
	void 네트워크_타임아웃_후_재시도하여_금융망_회원_조회에_성공한다() {
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withException(new SocketTimeoutException("read timed out")));
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"userId":"qwer@qwer.com","userKey":"test-user-key"}
								"""));

		FinanceMember member = client.findByEmail(EMAIL);

		assertThat(member.userKey()).isEqualTo(USER_KEY);
		server.verify();
	}

	@Test
	void Retry_After_헤더_값만큼_대기한_뒤_재시도한다() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
		MockRestServiceServer retryAfterServer = MockRestServiceServer.bindTo(builder).build();
		FinanceProperties properties = new FinanceProperties(
				URI.create(BASE_URL),
				API_KEY,
				Duration.ofSeconds(3),
				Duration.ofSeconds(5),
				2,
				Duration.ZERO,
				Duration.ofSeconds(2),
				Duration.ofSeconds(5)
		);
		FinanceMemberRestClient retryAfterClient =
				new FinanceMemberRestClient(builder.build(), properties, JsonMapper.builder().build(), new FinanceRetryExecutor(properties));

		retryAfterServer.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE)
						.header("Retry-After", "1"));
		retryAfterServer.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"userId":"qwer@qwer.com","userKey":"test-user-key"}
								"""));

		long startedAt = System.nanoTime();
		FinanceMember member = retryAfterClient.findByEmail(EMAIL);
		Duration elapsed = Duration.ofNanos(System.nanoTime() - startedAt);

		assertThat(member.userKey()).isEqualTo(USER_KEY);
		assertThat(elapsed).isGreaterThanOrEqualTo(Duration.ofMillis(900));
		retryAfterServer.verify();
	}

	@Test
	void Retry_After가_최대_대기_시간을_넘으면_재시도하지_않는다() {
		server.expect(ExpectedCount.once(), requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE)
						.header("Retry-After", "30"));

		assertFinanceError(FinanceErrorCode.SERVICE_UNAVAILABLE, () -> client.findByEmail(EMAIL));
		server.verify();
	}

	@Test
	void 업무_오류는_재시도하지_않고_한_번만_호출한다() {
		server.expect(ExpectedCount.once(), requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"responseCode":"E4003","responseMessage":"존재하지 않는 사용자입니다."}
								"""));

		assertFinanceError(FinanceErrorCode.MEMBER_NOT_FOUND, () -> client.findByEmail(EMAIL));
		server.verify();
	}

	@Test
	void 요청한_이메일과_응답_사용자가_다르면_잘못된_응답으로_처리한다() {
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"userId":"other@qwer.com","userKey":"test-user-key"}
								"""));

		assertFinanceError(FinanceErrorCode.INVALID_RESPONSE, () -> client.findByEmail(EMAIL));
	}

	@Test
	void JSON이_아닌_응답은_잘못된_응답으로_처리한다() {
		server.expect(requestTo(BASE_URL + "/member/search"))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.TEXT_PLAIN)
						.body("not-json"));

		assertFinanceError(FinanceErrorCode.INVALID_RESPONSE, () -> client.findByEmail(EMAIL));
	}

	@Test
	void 조회_입력_이메일은_비어_있을_수_없다() {
		assertThatIllegalArgumentException().isThrownBy(() -> client.findByEmail(" "));
	}

	@Test
	void 금융망_식별키는_toString에_노출하지_않는다() {
		FinanceMember member = new FinanceMember(EMAIL, USER_KEY);

		assertThat(member.toString())
				.doesNotContain(USER_KEY)
				.contains("userKey=******");
	}

	private void assertFinanceError(FinanceErrorCode expected, Runnable action) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(expected);
	}
}
