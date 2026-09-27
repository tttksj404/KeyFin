package com.finset.key_fin.global.firebase.service;

import java.util.Map;
import java.util.Objects;
import com.google.firebase.messaging.AndroidConfig;
import com.google.firebase.messaging.AndroidNotification;
import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.FirebaseMessagingException;
import com.google.firebase.messaging.Message;
import com.google.firebase.messaging.Notification;
import org.springframework.util.Assert;

public class FcmSender {

	private final FirebaseMessaging firebaseMessaging;

	public FcmSender(FirebaseMessaging firebaseMessaging) {
		this.firebaseMessaging = Objects.requireNonNull(firebaseMessaging, "firebaseMessaging must not be null");
	}

	/** FCM 접수 ID를 반환한다. 기기 수신 여부와 재시도·토큰 관리는 호출자가 처리한다. */
	public String send(String token, String title, String body, Map<String, String> data)
			throws FirebaseMessagingException {
		Assert.hasText(token, "FCM token must not be blank");
		Assert.hasText(title, "FCM title must not be blank");
		Assert.hasText(body, "FCM body must not be blank");
		Assert.notNull(data, "FCM data must not be null; use an empty map when no data is needed");

		Message message = Message.builder()
				.setToken(token)
				.setNotification(Notification.builder()
						.setTitle(title)
						.setBody(body)
						.build())
				.setAndroidConfig(AndroidConfig.builder()
						.setNotification(AndroidNotification.builder()
								.setChannelId("default")
								.build())
						.build())
				.putAllData(data)
				.build();
		return firebaseMessaging.send(message);
	}
}
