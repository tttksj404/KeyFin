package com.finset.key_fin.coaching.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withException;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

import java.io.IOException;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.ExpectedCount;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import com.finset.key_fin.coaching.dto.FdtBootstrap;
import com.finset.key_fin.coaching.dto.FdtSnapshot;
import com.finset.key_fin.coaching.dto.FdtTransaction;
import com.finset.key_fin.coaching.dto.TwinIdentity;

class CoachingTwinClientTest {

	private static final String BASE_URL = "https://coaching.example.com";
	private static final String TOKEN = "coaching-backend-token-0123456789abcdef";
	private static final String TWIN_URL = BASE_URL + "/v1/twin";
	private static final long USER_ID = 1L;
	private static final String IDENTITY_JSON = """
			{"user_id":"1","twin_id":"twin-abc","revision":1,"input_digest":"sha256:abc","as_of":"2026-09-10"}
			""";

	private MockRestServiceServer server;
	private CoachingTwinClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder()
				.baseUrl(BASE_URL)
				.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + TOKEN);
		server = MockRestServiceServer.bindTo(builder).build();
		client = new CoachingTwinClient(builder.build());
	}

	@Test
	void 인증과_멱등키_헤더를_실어_보낸다() {
		server.expect(requestTo(TWIN_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer " + TOKEN))
				.andExpect(header("Idempotency-Key", "key-1"))
				.andExpect(header("X-Coaching-User", "1"))
				.andExpect(content().contentType(MediaType.APPLICATION_JSON))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON).body(IDENTITY_JSON));

		TwinIdentity identity = client.create(USER_ID, bootstrap(), "key-1");

		assertThat(identity.twinId()).isEqualTo("twin-abc");
		assertThat(identity.revision()).isEqualTo(1L);
		server.verify();
	}

	@Test
	void 본문이_엔진_계약_이름으로_직렬화된다() {
		server.expect(requestTo(TWIN_URL))
				.andExpect(jsonPath("$.as_of").value("2026-09-10"))
				.andExpect(jsonPath("$.transactions[0].transaction_type").value("CARD"))
				.andExpect(jsonPath("$.transactions[0].amount_krw").value(4500))
				.andExpect(jsonPath("$.snapshot.reserve_krw").value(300000))
				.andExpect(jsonPath("$.envelopes[0].balance_krw").value(200000))
				.andExpect(jsonPath("$.budget_start_day").value(15))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON).body(IDENTITY_JSON));

		client.create(USER_ID, bootstrap(), "key-2");

		server.verify();
	}

	@Test
	void 키를_주지_않으면_매번_새로_만든다() {
		server.expect(ExpectedCount.twice(), requestTo(TWIN_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON).body(IDENTITY_JSON));

		client.create(USER_ID, bootstrap());
		client.create(USER_ID, bootstrap());

		server.verify();
	}

	@Test
	void 같은_사용자를_연속_두_번_보내도_거부되지_않는다() {
		server.expect(ExpectedCount.twice(), requestTo(TWIN_URL))
				.andRespond(withStatus(HttpStatus.OK)
						.contentType(MediaType.APPLICATION_JSON).body(IDENTITY_JSON));

		assertThat(client.create(USER_ID, bootstrap(), "key-3").twinId()).isEqualTo("twin-abc");
		assertThat(client.create(USER_ID, bootstrap(), "key-4").twinId()).isEqualTo("twin-abc");

		server.verify();
	}

	@Test
	void 응답에_모르는_필드가_있어도_읽는다() {
		server.expect(requestTo(TWIN_URL))
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.APPLICATION_JSON)
						.body("""
								{"user_id":"1","twin_id":"twin-abc","revision":2,
								 "input_digest":"sha256:abc","as_of":"2026-09-10","engine_commit":"deadbeef"}
								"""));

		assertThat(client.create(USER_ID, bootstrap(), "key-5").revision()).isEqualTo(2L);
	}

	@Test
	void 거래가_없으면_보내기_전에_막는다() {
		FdtBootstrap empty = new FdtBootstrap("2026-09-10", List.of(), snapshot(), List.of(), 1);

		assertThatIllegalArgumentException().isThrownBy(() -> client.create(USER_ID, empty, "key-6"));
		server.verify();
	}

	@Test
	void 서버_무응답은_장애로_올라간다() {
		server.expect(requestTo(TWIN_URL)).andRespond(withException(new IOException("read timed out")));

		assertThatThrownBy(() -> client.create(USER_ID, bootstrap(), "key-7"))
				.isInstanceOf(org.springframework.web.client.ResourceAccessException.class);
	}

	@Test
	void 서버_거부는_예외로_올라간다() {
		server.expect(requestTo(TWIN_URL)).andRespond(withStatus(HttpStatus.CONFLICT)
				.contentType(MediaType.APPLICATION_JSON).body("{\"detail\":\"twin_already_exists\"}"));

		assertThatThrownBy(() -> client.create(USER_ID, bootstrap(), "key-8"))
				.isInstanceOf(org.springframework.web.client.HttpClientErrorException.Conflict.class);
	}

	private FdtBootstrap bootstrap() {
		FdtTransaction transaction = new FdtTransaction(
				"1", "100", "LIVE", "CARD", "2026-09-10", "12:30:00", "식비", "카페",
				"메가MGC커피 선릉역점", "26", 4_500L, "", "7", "AUTO", "NORMAL", "NONE");
		return new FdtBootstrap("2026-09-10", List.of(transaction), snapshot(),
				List.of(new FdtBootstrap.Envelope("외식", 200_000L)), 15);
	}

	private FdtSnapshot snapshot() {
		return new FdtSnapshot("2026-09-10", "LIVE",
				List.of(new FdtSnapshot.Account("9700", 5_458_220L, false)),
				List.of(), List.of(), List.of(), 300_000L,
				Map.of("외식", 280_000L), FdtSnapshot.Coverage.NONE);
	}
}
