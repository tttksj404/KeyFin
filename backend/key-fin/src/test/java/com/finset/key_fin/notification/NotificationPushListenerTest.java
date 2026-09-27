package com.finset.key_fin.notification;

import java.util.List;
import java.util.Map;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.entity.PushDevice;
import com.finset.key_fin.notification.event.NotificationCreated;
import com.finset.key_fin.notification.service.NotificationPushListener;
import com.finset.key_fin.notification.service.NotificationPushPolicy.Decision;
import com.finset.key_fin.notification.service.NotificationPushRecipients;
import com.finset.key_fin.notification.service.NotificationPushRecipients.Selection;
import com.google.firebase.messaging.FirebaseMessagingException;
import com.google.firebase.messaging.MessagingErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.Mockito.*;

@ExtendWith(OutputCaptureExtension.class)
class NotificationPushListenerTest {
	private final NotificationPushRecipients recipients = mock(NotificationPushRecipients.class);
	private final FcmSender sender = mock(FcmSender.class);
	@SuppressWarnings("unchecked")
	private final ObjectProvider<FcmSender> provider = mock(ObjectProvider.class);
	private final NotificationPushListener listener = new NotificationPushListener(recipients, provider);

	@BeforeEach
	void setup() {
		when(provider.getIfAvailable()).thenReturn(sender);
	}

	@Test
	void unavailableFirebaseSkipsWithoutReadingSettings() {
		when(provider.getIfAvailable()).thenReturn(null);
		listener.onCreated(event("body", null));
		verifyNoInteractions(recipients, sender);
	}

	@ParameterizedTest
	@EnumSource(value = Decision.class, names = "ALLOW", mode = EnumSource.Mode.EXCLUDE)
	void deniedSelectionNeverCallsFcm(Decision reason) {
		when(recipients.select(1, NotificationType.TRANSFER_REQUEST)).thenReturn(new Selection(reason, List.of()));
		listener.onCreated(event("body", null));
		verifyNoInteractions(sender);
	}

	@ParameterizedTest
	@NullAndEmptySource
	@ValueSource(strings = {" ", "\t\n"})
	void missingBodyUsesTitleAndOmitsNullRef(String body) throws Exception {
		allow(device(10));
		listener.onCreated(event(body, null));
		verify(sender).send("secret-token-10", "private-title", "private-title",
				Map.of("notificationId", "123", "type", "TRANSFER_REQUEST", "requiresAction", "true"));
		verifyNoMoreInteractions(sender);
	}

	@Test
	void fcmFailureDoesNotPreventNextDeviceOrExposePayload(CapturedOutput output) throws Exception {
		allow(device(10), device(11));
		var failure = mock(FirebaseMessagingException.class);
		when(failure.getMessagingErrorCode()).thenReturn(MessagingErrorCode.UNREGISTERED);
		when(failure.getMessage()).thenReturn("secret-token-10 private-body");
		when(sender.send(eq("secret-token-10"), anyString(), anyString(), anyMap())).thenThrow(failure);
		listener.onCreated(event("private-body", "456"));
		for (long deviceId : new long[]{10, 11}) {
			verify(sender).send("secret-token-" + deviceId, "private-title", "private-body",
					Map.of("notificationId", "123", "type", "TRANSFER_REQUEST", "requiresAction", "true", "refId", "456"));
		}
		verifyNoMoreInteractions(sender);
		assertThat(output.getAll()).contains("UNREGISTERED", "deviceId=11 result=ACCEPTED")
				.doesNotContain("secret-token", "private-title", "private-body");
	}

	@Test
	void unexpectedSendFailureIsIsolatedPerDevice() throws Exception {
		allow(device(10), device(11));
		when(sender.send(eq("secret-token-10"), anyString(), anyString(), anyMap()))
				.thenThrow(new IllegalStateException("sensitive"));
		assertThatCode(() -> listener.onCreated(event("body", null))).doesNotThrowAnyException();
		verify(sender).send(eq("secret-token-11"), anyString(), anyString(), anyMap());
	}

	@Test
	void lookupFailureDoesNotEscapeOrExposeExceptionMessage(CapturedOutput output) {
		when(recipients.select(1, NotificationType.TRANSFER_REQUEST)).thenThrow(new IllegalStateException("sensitive"));
		assertThatCode(() -> listener.onCreated(event("body", null))).doesNotThrowAnyException();
		verifyNoInteractions(sender);
		assertThat(output.getAll()).contains("PREPARATION_ERROR").doesNotContain("sensitive");
	}

	private void allow(PushDevice... devices) {
		when(recipients.select(1, NotificationType.TRANSFER_REQUEST)).thenReturn(new Selection(Decision.ALLOW, List.of(devices)));
	}

	private PushDevice device(long id) {
		return new PushDevice(id, 1, "installation-" + id, "secret-token-" + id, "ANDROID", true, null);
	}

	private NotificationCreated event(String body, String refId) {
		return new NotificationCreated(123, 1, NotificationType.TRANSFER_REQUEST, "private-title", body, refId, true);
	}
}
