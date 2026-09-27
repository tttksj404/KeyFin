package com.finset.key_fin.coaching.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class CoachingEnvelopeReviewClientTest {

	private static final String BASE_URL = "https://coaching.example.com";

	@Test
	void 봉투와_구간을_보내고_문장을_읽는다() {
		RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL)
				.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer coaching-backend-token-0123456789abcdef");
		MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
		CoachingEnvelopeReviewClient client = new CoachingEnvelopeReviewClient(builder.build());
		server.expect(requestTo(BASE_URL + "/v1/coaching/envelope-reviews"))
				.andExpect(method(HttpMethod.POST))
				.andExpect(header("Idempotency-Key", "alert-feedback-91"))
				.andExpect(header("X-Coaching-User", "6"))
				.andExpect(jsonPath("$.envelope").value("외식"))
				.andExpect(jsonPath("$.tier").value("20"))
				.andRespond(withStatus(HttpStatus.OK).contentType(MediaType.APPLICATION_JSON).body("""
						{"id":"env-1","envelope":"외식","tier":"20","remaining_krw":18000,"budget_krw":100000,
						 "text":"남은 날에 비해 외식이 빠르게 줄고 있어요.","wording_source":"template"}
						"""));

		assertThat(client.review(6L, "외식", "20", "alert-feedback-91").text())
				.isEqualTo("남은 날에 비해 외식이 빠르게 줄고 있어요.");
		server.verify();
	}
}
