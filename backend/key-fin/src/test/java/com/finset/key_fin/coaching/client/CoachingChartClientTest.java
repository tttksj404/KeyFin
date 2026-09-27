package com.finset.key_fin.coaching.client;

import org.hamcrest.Matchers;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

import com.finset.key_fin.coaching.dto.ChartHint;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

class CoachingChartClientTest {

	private static final String BASE_URL = "https://coaching.example.com";
	private static final String TOKEN = "coaching-backend-token-0123456789abcdef";
	private static final long USER_ID = 970L;
	private static final String CHART_JSON = """
			{"id":"8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f","chart":{"id":"8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f","totalForecast":123},
			 "wording":{"text":"예산 안에서 끝날 것 같아요.","source":"template"},"receipt":{},"created_at":1789000300.0}
			""";

	private MockRestServiceServer server;
	private CoachingChartClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder()
				.baseUrl(BASE_URL)
				.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + TOKEN)
				.defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE);
		server = MockRestServiceServer.bindTo(builder).build();
		client = new CoachingChartClient(builder.build());
	}

	@Test
	void 차트_생성은_힌트를_본문으로_보내고_id를_읽는다() {
		server.expect(requestTo(BASE_URL + "/v1/charts/budget-forecast"))
				.andExpect(method(HttpMethod.POST))
				.andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer " + TOKEN))
				.andExpect(header("Idempotency-Key", "chart-coach-1"))
				.andExpect(header("X-Coaching-User", "970"))
				.andExpect(jsonPath("$.period_start").value("2026-09-01"))
				.andExpect(jsonPath("$.question").value("이번 달 예산 어때?"))
				.andExpect(jsonPath("$.purchase").doesNotExist())
				.andExpect(jsonPath("$.endpoint").doesNotExist())
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.APPLICATION_JSON).body(CHART_JSON));

		String chartId = client.create(USER_ID, new ChartHint("2026-09-01", "이번 달 예산 어때?", null), "chart-coach-1").id();

		assertThat(chartId).isEqualTo("8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f");
		server.verify();
	}

	@Test
	void 구매_힌트는_purchase_블록을_그대로_보낸다() {
		server.expect(requestTo(BASE_URL + "/v1/charts/budget-forecast"))
				.andExpect(jsonPath("$.purchase.envelope").value("취미·여가"))
				.andExpect(jsonPath("$.purchase.amount_krw").value(300000))
				.andExpect(jsonPath("$.purchase.on_date").value("2026-09-28"))
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.APPLICATION_JSON).body(CHART_JSON));

		client.create(USER_ID, new ChartHint("2026-09-01", "노트북 사도 돼?",
				new ChartHint.Purchase("취미·여가", 300_000L, "2026-09-28")), "chart-coach-2");

		server.verify();
	}

	@Test
	void 차트_HTML은_text_html로_요청해_본문을_그대로_돌려준다() {
		server.expect(requestTo(BASE_URL + "/v1/charts/8f1c2d3e/html"))
				.andExpect(method(HttpMethod.GET))
				.andExpect(header(HttpHeaders.ACCEPT, Matchers.containsString(MediaType.TEXT_HTML_VALUE)))
				.andExpect(header("X-Coaching-User", "970"))
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.TEXT_HTML).body("<!doctype html><html><body>chart</body></html>"));

		assertThat(client.html(USER_ID, "8f1c2d3e")).startsWith("<!doctype html>");
		server.verify();
	}

	@Test
	void 다른_사용자의_차트는_404가_그대로_올라온다() {
		server.expect(requestTo(BASE_URL + "/v1/charts/other/html"))
				.andRespond(withStatus(HttpStatus.NOT_FOUND).contentType(MediaType.APPLICATION_JSON).body("{\"error\":\"resource_not_found\"}"));

		assertThatThrownBy(() -> client.html(USER_ID, "other")).isInstanceOf(HttpClientErrorException.NotFound.class);
		server.verify();
	}

	@Test
	void 생성_응답에_모르는_필드가_있어도_읽는다() {
		server.expect(requestTo(BASE_URL + "/v1/charts/budget-forecast"))
				.andExpect(content().contentType(MediaType.APPLICATION_JSON))
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.APPLICATION_JSON).body(CHART_JSON));

		assertThat(client.create(USER_ID, new ChartHint("2026-09-01", null, null), "k").id()).hasSize(32);
		server.verify();
	}
}
