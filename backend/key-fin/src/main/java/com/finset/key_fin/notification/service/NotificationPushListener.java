package com.finset.key_fin.notification.service;

import java.util.HashMap;
import java.util.Map;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.finset.key_fin.notification.entity.PushDevice;
import com.finset.key_fin.notification.event.NotificationCreated;
import com.finset.key_fin.notification.service.NotificationPushPolicy.Decision;
import com.google.firebase.messaging.FirebaseMessagingException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Slf4j
@Component
@RequiredArgsConstructor
public class NotificationPushListener {
	private final NotificationPushRecipients recipients;
	private final ObjectProvider<FcmSender> senderProvider;

	@Transactional(propagation = Propagation.NOT_SUPPORTED)
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void onCreated(NotificationCreated event) {
		try {
			FcmSender sender = senderProvider.getIfAvailable();
			if (sender == null) {
				log.info("notificationId={} result=FCM_DISABLED", event.notificationId());
				return;
			}
			var selection = recipients.select(event.userId(), event.type());
			if (selection.decision() != Decision.ALLOW) {
				log.info("notificationId={} result={}", event.notificationId(), selection.decision());
				return;
			}
			Map<String, String> data = new HashMap<>();
			data.put("notificationId", Long.toString(event.notificationId()));
			data.put("type", event.type().name());
			data.put("requiresAction", Boolean.toString(event.requiresAction()));
			if (event.refId() != null) data.put("refId", event.refId());
			String body = event.body() == null || event.body().isBlank() ? event.title() : event.body();
			for (PushDevice device : selection.devices()) {
				try {
					sender.send(device.fcmToken(), event.title(), body, data);
					log.info("notificationId={} deviceId={} result=ACCEPTED", event.notificationId(), device.id());
				} catch (FirebaseMessagingException e) {
					log.warn("notificationId={} deviceId={} result=FAILED code={}",
							event.notificationId(), device.id(), e.getMessagingErrorCode());
				} catch (RuntimeException e) {
					log.warn("notificationId={} deviceId={} result=FAILED code=UNEXPECTED_ERROR",
							event.notificationId(), device.id());
				}
			}
		} catch (RuntimeException e) {
			log.warn("notificationId={} result=FAILED code=PREPARATION_ERROR", event.notificationId());
		}
	}
}
