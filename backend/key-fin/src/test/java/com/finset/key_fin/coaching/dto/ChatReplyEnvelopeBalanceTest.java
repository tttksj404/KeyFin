package com.finset.key_fin.coaching.dto;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import tools.jackson.databind.json.JsonMapper;

class ChatReplyEnvelopeBalanceTest {

	private final JsonMapper mapper = JsonMapper.builder().build();

	@Test
	void 코칭이_싣은_봉투_잔액_표를_앱_응답으로_그대로_옮긴다() {
		String turnJson = """
				{"id":"coach-9","text":"봉투별 남은 잔액은 아래 표에 정리했어요.","wording_source":"template",
				 "receipt":{"trigger":"dialogue"},
				 "envelope_balances":[{"envelope":"외식","balance_krw":343700},{"envelope":"교통비","balance_krw":150000}]}
				""";

		ChatReply reply = ChatReply.from(mapper.readValue(turnJson, CoachingTurnReply.class), null);

		assertThat(reply.envelopeBalances()).containsExactly(
				new ChatReply.EnvelopeBalance("외식", 343_700L),
				new ChatReply.EnvelopeBalance("교통비", 150_000L));
	}

	@Test
	void 표가_없는_이전_코칭_응답은_빈_목록이다() {
		String turnJson = """
				{"id":"coach-1","text":"예측 답변","wording_source":"llm","receipt":{"trigger":"forecast"}}
				""";

		ChatReply reply = ChatReply.from(mapper.readValue(turnJson, CoachingTurnReply.class), null);

		assertThat(reply.envelopeBalances()).isEmpty();
	}
}
