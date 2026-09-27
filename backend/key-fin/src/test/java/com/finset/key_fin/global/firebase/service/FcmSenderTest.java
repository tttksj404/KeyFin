package com.finset.key_fin.global.firebase.service;

import java.io.IOException;
import java.util.Map;
import com.google.api.client.json.gson.GsonFactory;
import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.FirebaseMessagingException;
import com.google.firebase.messaging.Message;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class FcmSenderTest {

	private static final String TOKEN = "test-device-token";
	private static final String TITLE = "KeyFin 서버 테스트";
	private static final String BODY = "Spring Boot에서 보낸 알림입니다.";
	private static final String MESSAGE_ID = "projects/keyfin-test/messages/test-message";

	@Mock
	private FirebaseMessaging firebaseMessaging;

	private FcmSender sender;

	@BeforeEach
	void setUp() {
		sender = new FcmSender(firebaseMessaging);
	}

	@Test
	@DisplayName("대상·표시 문구·문자열 데이터·Android 채널을 보내고 접수 ID를 반환한다")
	void sendsNotificationAndDataToToken() throws FirebaseMessagingException, IOException {
		when(firebaseMessaging.send(any(Message.class))).thenReturn(MESSAGE_ID);

		String result = sender.send(TOKEN, TITLE, BODY, Map.of("type", "TRANSFER_REQUEST", "refId", "456"));

		assertThat(result).isEqualTo(MESSAGE_ID);
		JsonObject payload = sentPayload();
		assertThat(payload.get("token").getAsString()).isEqualTo(TOKEN);
		assertThat(payload.getAsJsonObject("notification").get("title").getAsString()).isEqualTo(TITLE);
		assertThat(payload.getAsJsonObject("notification").get("body").getAsString()).isEqualTo(BODY);
		assertThat(payload.getAsJsonObject("data").get("type").getAsString()).isEqualTo("TRANSFER_REQUEST");
		assertThat(payload.getAsJsonObject("data").get("refId").getAsString()).isEqualTo("456");
		assertThat(payload.getAsJsonObject("android").getAsJsonObject("notification")
				.get("channel_id").getAsString()).isEqualTo("default");
		verifyNoMoreInteractions(firebaseMessaging);
	}

	@Test
	@DisplayName("부가 데이터가 없어도 빈 Map으로 발송할 수 있다")
	void sendsWithoutData() throws FirebaseMessagingException, IOException {
		when(firebaseMessaging.send(any(Message.class))).thenReturn(MESSAGE_ID);

		assertThat(sender.send(TOKEN, TITLE, BODY, Map.of())).isEqualTo(MESSAGE_ID);
		// Firebase SDK는 비어 있는 data 필드를 발송 JSON에서 생략한다.
		assertThat(sentPayload().has("data")).isFalse();
	}

	@Test
	@DisplayName("FCM 오류를 변경하거나 자체 재시도하지 않고 호출자에게 전달한다")
	void propagatesFirebaseFailureWithoutRetry() throws FirebaseMessagingException {
		FirebaseMessagingException failure = mock(FirebaseMessagingException.class);
		when(firebaseMessaging.send(any(Message.class))).thenThrow(failure);

		assertThatThrownBy(() -> sender.send(TOKEN, TITLE, BODY, Map.of())).isSameAs(failure);
		verify(firebaseMessaging).send(any(Message.class));
		verifyNoMoreInteractions(firebaseMessaging);
	}

	@ParameterizedTest
	@NullAndEmptySource
	@ValueSource(strings = {" ", "\t\n"})
	@DisplayName("빈 토큰은 발송 전에 거절한다")
	void rejectsBlankToken(String token) {
		assertThatThrownBy(() -> sender.send(token, TITLE, BODY, Map.of()))
				.isInstanceOf(IllegalArgumentException.class);
		verifyNoInteractions(firebaseMessaging);
	}

	@ParameterizedTest
	@NullAndEmptySource
	@ValueSource(strings = {" ", "\t\n"})
	@DisplayName("빈 제목은 발송 전에 거절한다")
	void rejectsBlankTitle(String title) {
		assertThatThrownBy(() -> sender.send(TOKEN, title, BODY, Map.of()))
				.isInstanceOf(IllegalArgumentException.class);
		verifyNoInteractions(firebaseMessaging);
	}

	@ParameterizedTest
	@NullAndEmptySource
	@ValueSource(strings = {" ", "\t\n"})
	@DisplayName("빈 본문은 발송 전에 거절한다")
	void rejectsBlankBody(String body) {
		assertThatThrownBy(() -> sender.send(TOKEN, TITLE, body, Map.of()))
				.isInstanceOf(IllegalArgumentException.class);
		verifyNoInteractions(firebaseMessaging);
	}

	@Test
	@DisplayName("null 데이터는 발송 전에 거절한다")
	void rejectsNullData() {
		assertThatThrownBy(() -> sender.send(TOKEN, TITLE, BODY, null))
				.isInstanceOf(IllegalArgumentException.class);
		verifyNoInteractions(firebaseMessaging);
	}

	private JsonObject sentPayload() throws FirebaseMessagingException, IOException {
		ArgumentCaptor<Message> captor = ArgumentCaptor.forClass(Message.class);
		verify(firebaseMessaging).send(captor.capture());
		// SDK와 같은 JSON 직렬화를 사용해 내부 필드가 아닌 실제 발송 필드명을 검증한다.
		return JsonParser.parseString(GsonFactory.getDefaultInstance().toString(captor.getValue())).getAsJsonObject();
	}
}
