package com.finset.key_fin.coaching.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;

import com.finset.key_fin.coaching.client.CoachingChartClient;
import com.finset.key_fin.coaching.client.CoachingChatClient;
import com.finset.key_fin.coaching.client.CoachingTwinClient;
import com.finset.key_fin.coaching.dto.ChatHistoryResponse;
import com.finset.key_fin.coaching.dto.ChartCreated;
import com.finset.key_fin.coaching.dto.ChartHint;
import com.finset.key_fin.coaching.dto.SpendingRow;
import com.finset.key_fin.coaching.dto.ChatReply;
import com.finset.key_fin.coaching.dto.CoachingNumericRows;
import com.finset.key_fin.coaching.dto.CoachingSessionView;
import com.finset.key_fin.coaching.dto.CoachingTurnReply;
import com.finset.key_fin.coaching.dto.FdtBootstrap;
import com.finset.key_fin.coaching.entity.CoachingSession;
import com.finset.key_fin.coaching.exception.CoachingErrorCode;
import com.finset.key_fin.coaching.repository.CoachingSessionRepository;
import com.finset.key_fin.global.exception.BusinessException;

class CoachingChatServiceTest {

	private static final long USER_ID = 970L;
	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
	private static final Instant NOW = Instant.parse("2026-09-10T03:00:00Z");
	private static final double NEW_EXPIRES = NOW.getEpochSecond() + 86400;

	private final CoachingSessionRepository sessionRepository = mock(CoachingSessionRepository.class);
	private final CoachingChatClient chatClient = mock(CoachingChatClient.class);
	private final CoachingTwinClient twinClient = mock(CoachingTwinClient.class);
	private final CoachingChartClient chartClient = mock(CoachingChartClient.class);
	private final CoachingChartStore chartStore = mock(CoachingChartStore.class);
	private final FdtBootstrapService bootstrapService = mock(FdtBootstrapService.class);
	private final FdtBootstrap bootstrap = mock(FdtBootstrap.class);

	private CoachingChatService service;

	@BeforeEach
	void setUp() {
		service = new CoachingChatService(sessionRepository, chatClient, twinClient, chartClient, chartStore, bootstrapService,
				Clock.fixed(NOW, SEOUL));
		given(bootstrapService.build(USER_ID)).willReturn(bootstrap);
		given(sessionRepository.save(any(CoachingSession.class))).willAnswer(inv -> inv.getArgument(0));
	}

	@Test
	void 세션이_없으면_트윈을_보내고_세션을_만든_뒤_질문한다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.empty());
		given(chatClient.createSession(USER_ID)).willReturn(new CoachingSessionView("sess-new", NEW_EXPIRES, List.of()));
		given(chatClient.sendMessage(USER_ID, "sess-new", "복리가 뭐야?")).willReturn(chatAnswer("answered", "llm"));

		ChatReply reply = service.chat(USER_ID, "복리가 뭐야?");

		verify(twinClient).create(USER_ID, bootstrap);
		verify(sessionRepository).save(any(CoachingSession.class));
		assertThat(reply.kind()).isEqualTo(ChatReply.Kind.CHAT);
		assertThat(reply.status()).isEqualTo("answered");
		assertThat(reply.source()).isEqualTo("llm");
		assertThat(reply.answerId()).isEqualTo("ans-1");
	}

	@Test
	void 유효한_세션이_있으면_트윈만_다시_보내고_세션은_다시_만들지_않는다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.sendMessage(USER_ID, "sess-live", "월말 예측")).willReturn(coaching());

		ChatReply reply = service.chat(USER_ID, "월말 예측");

		verify(twinClient).create(USER_ID, bootstrap);
		verify(chatClient, never()).createSession(anyLong());
		assertThat(reply.kind()).isEqualTo(ChatReply.Kind.COACHING);
		assertThat(reply.status()).isEqualTo("answered");
		assertThat(reply.answerId()).isEqualTo("coach-1");
	}

	@Test
	void 만료된_세션은_같은_행을_새_세션으로_바꾼다() {
		CoachingSession expired = session("sess-old", -60);
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(expired));
		given(chatClient.createSession(USER_ID)).willReturn(new CoachingSessionView("sess-new", NEW_EXPIRES, List.of()));
		given(chatClient.sendMessage(USER_ID, "sess-new", "질문")).willReturn(chatAnswer("answered", "engine"));

		service.chat(USER_ID, "질문");

		verify(twinClient).create(USER_ID, bootstrap);
		assertThat(expired.getSessionId()).isEqualTo("sess-new");
		assertThat(expired.getExpiresAt()).isEqualTo(LocalDateTime.ofInstant(NOW.plusSeconds(86400), SEOUL));
	}

	@Test
	void 코칭_서버가_410으로_거절하면_새_세션으로_한_번_다시_보낸다() {
		CoachingSession live = session("sess-live", 60);
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(live));
		given(chatClient.sendMessage(USER_ID, "sess-live", "질문")).willThrow(clientError(HttpStatus.GONE));
		given(chatClient.createSession(USER_ID)).willReturn(new CoachingSessionView("sess-new", NEW_EXPIRES, List.of()));
		given(chatClient.sendMessage(USER_ID, "sess-new", "질문")).willReturn(chatAnswer("answered", "llm"));

		ChatReply reply = service.chat(USER_ID, "질문");

		assertThat(reply.answerId()).isEqualTo("ans-1");
		assertThat(live.getSessionId()).isEqualTo("sess-new");
		verify(twinClient).create(USER_ID, bootstrap);
	}

	@Test
	void 세션_외_4xx_거절은_AI_003_연결_실패는_AI_001이다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.sendMessage(USER_ID, "sess-live", "a"))
				.willThrow(clientError(HttpStatus.UNPROCESSABLE_ENTITY, "{\"error\":\"period_clarification_required\"}"));
		given(chatClient.sendMessage(USER_ID, "sess-live", "b")).willThrow(new ResourceAccessException("timeout"));

		assertThatThrownBy(() -> service.chat(USER_ID, "a"))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(CoachingErrorCode.COACHING_REJECTED);
		assertThatThrownBy(() -> service.chat(USER_ID, "b"))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(CoachingErrorCode.COACHING_UNAVAILABLE);
		verify(chatClient, never()).createSession(anyLong());
	}

	@Test
	void 트윈_전송이_실패해도_경고만_남기고_대화는_이어진다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(twinClient.create(USER_ID, bootstrap))
				.willThrow(clientError(HttpStatus.UNPROCESSABLE_ENTITY))
				.willThrow(new ResourceAccessException("timeout"));
		given(chatClient.sendMessage(USER_ID, "sess-live", "질문")).willReturn(chatAnswer("answered", "llm"));

		assertThat(service.chat(USER_ID, "질문").answerId()).isEqualTo("ans-1");
		assertThat(service.chat(USER_ID, "질문").answerId()).isEqualTo("ans-1");
		verify(chatClient, never()).createSession(anyLong());
	}

	@Test
	void 이력은_세션이_없거나_만료됐으면_비어_있다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.empty(), Optional.of(session("sess-old", -1)));

		assertThat(service.history(USER_ID).messages()).isEmpty();
		assertThat(service.history(USER_ID).messages()).isEmpty();
		verify(chatClient, never()).getSession(anyLong(), anyString());
	}

	@Test
	void 이력은_코칭_서버_메시지를_그대로_돌려주고_닫힌_세션이면_비운다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.getSession(USER_ID, "sess-live"))
				.willReturn(new CoachingSessionView("sess-live", NEW_EXPIRES, List.of(
						new CoachingSessionView.Message("user", "복리가 뭐야?", null),
						new CoachingSessionView.Message("assistant", "이자에 이자가 붙어요.",
								new CoachingSessionView.AnswerReference("chat", "ans-9")))))
				.willThrow(clientError(HttpStatus.GONE));

		ChatHistoryResponse history = service.history(USER_ID);
		assertThat(history.messages()).extracting(ChatHistoryResponse.Entry::content)
				.containsExactly("복리가 뭐야?", "이자에 이자가 붙어요.");
		assertThat(history.expiresAt()).isEqualTo(LocalDateTime.ofInstant(NOW.plusSeconds(86400), SEOUL));
		assertThat(history.messages()).extracting(ChatHistoryResponse.Entry::chartId).containsExactly(null, null);

		assertThat(service.history(USER_ID).messages()).isEmpty();
	}

	@Test
	void chart_hint가_있으면_답변_id_멱등키로_차트를_만들고_세션_만료까지_기억한다() {
		CoachingSession live = session("sess-live", 3600);
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(live));
		given(chatClient.sendMessage(USER_ID, "sess-live", "이번 달 예산 어때?")).willReturn(coachingWithChart());
		given(chartClient.create(eq(USER_ID), any(ChartHint.class), eq("chart-coach-2")))
				.willReturn(new ChartCreated("8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f"));

		ChatReply reply = service.chat(USER_ID, "이번 달 예산 어때?");

		assertThat(reply.kind()).isEqualTo(ChatReply.Kind.COACHING);
		assertThat(reply.chartId()).isEqualTo("8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f");
		assertThat(reply.rows()).isEmpty();
		verify(chartStore).save(USER_ID, "coach-2", "8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f", Duration.ofSeconds(3600));
	}

	@Test
	void chart_hint가_없으면_차트를_만들지_않고_chartId는_null이다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.sendMessage(USER_ID, "sess-live", "질문")).willReturn(coaching());

		assertThat(service.chat(USER_ID, "질문").chartId()).isNull();
		verify(chartClient, never()).create(anyLong(), any(), anyString());
		verify(chartStore, never()).save(anyLong(), anyString(), anyString(), any());
	}

	@Test
	void 차트_생성이_실패해도_답변은_그대로_내려가고_chartId만_null이다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.sendMessage(USER_ID, "sess-live", "이번 달 예산 어때?")).willReturn(coachingWithChart());
		given(chartClient.create(eq(USER_ID), any(ChartHint.class), anyString()))
				.willThrow(clientError(HttpStatus.UNPROCESSABLE_ENTITY));

		ChatReply reply = service.chat(USER_ID, "이번 달 예산 어때?");

		assertThat(reply.reply()).isEqualTo("예측 답변");
		assertThat(reply.chartId()).isNull();
		verify(chartStore, never()).save(anyLong(), anyString(), anyString(), any());
	}

	@Test
	void 소비_조회_답변의_rows와_totalKrw를_camelCase로_통과시킨다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.sendMessage(USER_ID, "sess-live", "이번 달 얼마 썼어?")).willReturn(
				new CoachingTurnReply("ans-5", "spending_history", "answered", "외식 45,000원", "engine", null, null, null,
						List.of(new SpendingRow("외식", 45_000L, 3)), 45_000L, null));

		ChatReply reply = service.chat(USER_ID, "이번 달 얼마 썼어?");

		assertThat(reply.rows()).containsExactly(new ChatReply.Row("외식", 45_000L, 3));
		assertThat(reply.totalKrw()).isEqualTo(45_000L);
		assertThat(reply.chartId()).isNull();
	}

	@Test
	void 이력의_assistant_메시지는_기억해_둔_차트_id를_붙인다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.getSession(USER_ID, "sess-live"))
				.willReturn(new CoachingSessionView("sess-live", NEW_EXPIRES, List.of(
						new CoachingSessionView.Message("user", "이번 달 예산 어때?", null),
						new CoachingSessionView.Message("assistant", "예측 답변",
								new CoachingSessionView.AnswerReference("coaching", "coach-2")))));
		given(chartStore.find(USER_ID, "coach-2")).willReturn(Optional.of("8f1c2d3e"));

		assertThat(service.history(USER_ID).messages()).extracting(ChatHistoryResponse.Entry::chartId)
				.containsExactly(null, "8f1c2d3e");
	}

	@Test
	void 차트_HTML은_404면_AI_002_그_외_4xx는_AI_003_장애는_AI_001이다() {
		given(chartClient.html(USER_ID, "missing")).willThrow(clientError(HttpStatus.NOT_FOUND));
		given(chartClient.html(USER_ID, "bad")).willThrow(clientError(HttpStatus.UNPROCESSABLE_ENTITY));
		given(chartClient.html(USER_ID, "down")).willThrow(new ResourceAccessException("timeout"));
		given(chartClient.html(USER_ID, "ok")).willReturn("<!doctype html>");

		assertThatThrownBy(() -> service.chartHtml(USER_ID, "missing"))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(CoachingErrorCode.CHART_NOT_FOUND);
		assertThatThrownBy(() -> service.chartHtml(USER_ID, "bad"))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(CoachingErrorCode.COACHING_REJECTED);
		assertThatThrownBy(() -> service.chartHtml(USER_ID, "down"))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(CoachingErrorCode.COACHING_UNAVAILABLE);
		assertThat(service.chartHtml(USER_ID, "ok")).isEqualTo("<!doctype html>");
	}

	@Test
	void 위험_답변의_numeric_rows를_camelCase로_통과시키고_없으면_null이다() {
		given(sessionRepository.findByUserId(USER_ID)).willReturn(Optional.of(session("sess-live", 60)));
		given(chatClient.sendMessage(USER_ID, "sess-live", "돈 모자랄까?")).willReturn(
				new CoachingTurnReply("coach-7", null, null, "위험 답변", "template", null, Map.of("trigger", "risk"),
						null, null, null, new CoachingNumericRows("risk",
								List.of(new CoachingNumericRows.EnvelopeSpend("외식", 100_000L, 150_000L, 240_000L)),
								List.of(new CoachingNumericRows.BudgetRisk("외식", 297_000L, 63_800L, 213_800L, 0.12)))));
		given(chatClient.sendMessage(USER_ID, "sess-live", "질문")).willReturn(coaching());

		ChatReply risk = service.chat(USER_ID, "돈 모자랄까?");
		ChatReply plain = service.chat(USER_ID, "질문");

		assertThat(risk.numericRows().mode()).isEqualTo("risk");
		assertThat(risk.numericRows().envelopeSpend())
				.containsExactly(new ChatReply.NumericRows.EnvelopeSpend("외식", 100_000L, 150_000L, 240_000L));
		assertThat(risk.numericRows().budgetRisk())
				.containsExactly(new ChatReply.NumericRows.BudgetRisk("외식", 297_000L, 63_800L, 213_800L, 0.12));
		assertThat(plain.numericRows()).isNull();
	}

	private static CoachingSession session(String sessionId, long secondsFromNow) {
		return CoachingSession.open(USER_ID, sessionId,
				LocalDateTime.ofInstant(NOW.plusSeconds(secondsFromNow), SEOUL));
	}

	private static CoachingTurnReply chatAnswer(String status, String source) {
		return new CoachingTurnReply("ans-1", "finance_education", status, "답변", source, null, null, null, null, null, null);
	}

	private static CoachingTurnReply coaching() {
		return new CoachingTurnReply("coach-1", null, null, "예측 답변", "llm", null,
				Map.of("trigger", "forecast"), null, null, null, null);
	}

	private static CoachingTurnReply coachingWithChart() {
		return new CoachingTurnReply("coach-2", null, null, "예측 답변", "llm", null,
				Map.of("trigger", "forecast"), new ChartHint("2026-09-01", "이번 달 예산 어때?", null), null, null, null);
	}

	private static HttpClientErrorException clientError(HttpStatus status) {
		return clientError(status, "");
	}

	private static HttpClientErrorException clientError(HttpStatus status, String body) {
		return HttpClientErrorException.create(status, status.getReasonPhrase(), HttpHeaders.EMPTY,
				body.getBytes(StandardCharsets.UTF_8), StandardCharsets.UTF_8);
	}
}
