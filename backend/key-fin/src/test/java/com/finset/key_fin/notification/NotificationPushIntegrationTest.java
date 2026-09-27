package com.finset.key_fin.notification;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.UUID;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class NotificationPushIntegrationTest extends SpringIntegrationTestSupport {
	private static final long USER = 71001;
	@Autowired NotificationService notifications;
	@Autowired JdbcClient jdbc;
	@Autowired PlatformTransactionManager transactionManager;

	@BeforeEach
	void setup() {
		Clock fixed = Clock.fixed(Instant.parse("2026-09-18T14:00:00Z"), ZoneOffset.UTC); // KST 23:00
		testClock.set(fixed.instant());
		cleanup();
		jdbc.sql("INSERT INTO users(id,email,password,name) VALUES (:id,'push-policy@test.invalid','test','A')")
				.param("id", USER).update();
		jdbc.sql("INSERT INTO user_settings(user_id) VALUES (:id)").param("id", USER).update();
		device("active-token", true);
		device("inactive-token", false);
	}

	@AfterEach
	void cleanup() {
		for (String table : new String[]{"notifications", "push_devices", "user_settings"}) {
			jdbc.sql("DELETE FROM " + table + " WHERE user_id = :id").param("id", USER).update();
		}
		jdbc.sql("DELETE FROM users WHERE id = :id").param("id", USER).update();
	}

	@Test
	void sendsOnlyAfterOuterCommitOutsideTransactionAndOnlyToActiveDevices() throws Exception {
		when(sender.send(anyString(), anyString(), anyString(), anyMap())).thenAnswer(invocation -> {
			assertThat(TransactionSynchronizationManager.isActualTransactionActive()).isFalse();
			assertThat(count()).isEqualTo(1);
			return "accepted";
		});
		long id = new TransactionTemplate(transactionManager).execute(status -> {
			long saved = create(NotificationType.TRANSFER_REQUEST);
			verifyNoInteractions(sender);
			return saved;
		});
		verify(sender).send("active-token", "title", "body", java.util.Map.of(
				"notificationId", Long.toString(id), "type", "TRANSFER_REQUEST", "requiresAction", "true", "refId", "456"));
		verifyNoMoreInteractions(sender);
	}

	@Test
	void rollbackRemovesInboxAndNeverSends() {
		new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
			create(NotificationType.COACHING);
			assertThat(count()).isEqualTo(1);
			verifyNoInteractions(sender);
			status.setRollbackOnly();
		});
		assertThat(count()).isZero();
		verifyNoInteractions(sender);
	}

	@ParameterizedTest
	@ValueSource(strings = {"OFF", "QUIET", "MISSING", "INVALID", "SAME_TIME"})
	void suppressionPreservesInbox(String reason) {
		switch (reason) {
			case "OFF" -> jdbc.sql("UPDATE user_settings SET noti_coaching = FALSE WHERE user_id = :id").param("id", USER).update();
			case "QUIET" -> jdbc.sql("UPDATE user_settings SET quiet_hours_start = '23:00', quiet_hours_end = '08:00' WHERE user_id = :id").param("id", USER).update();
			case "MISSING" -> jdbc.sql("DELETE FROM user_settings WHERE user_id = :id").param("id", USER).update();
			case "INVALID" -> jdbc.sql("UPDATE user_settings SET quiet_hours_start = '23:00' WHERE user_id = :id").param("id", USER).update();
			case "SAME_TIME" -> jdbc.sql("UPDATE user_settings SET quiet_hours_start = '23:00', quiet_hours_end = '23:00' WHERE user_id = :id").param("id", USER).update();
		}
		long id = create(NotificationType.COACHING);
		assertThat(notifications.list(USER, false, null, null).items()).extracting("id").containsExactly(id);
		verifyNoInteractions(sender);
	}

	@Test
	void readsSettingsChangedInCreationTransactionAfterCommit() {
		new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
			create(NotificationType.COACHING);
			jdbc.sql("UPDATE user_settings SET noti_coaching = FALSE WHERE user_id = :id").param("id", USER).update();
		});
		assertThat(count()).isEqualTo(1);
		verifyNoInteractions(sender);
	}

	@Test
	void deletedUserIsExcludedAtDispatchEvenIfActiveWhenCreated() {
		new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
			create(NotificationType.WARNING);
			jdbc.sql("UPDATE users SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id").param("id", USER).update();
		});
		assertThat(count()).isEqualTo(1);
		verifyNoInteractions(sender);
	}

	@Test
	void fcmFailureDoesNotFailCreationOrLoseInbox() throws Exception {
		when(sender.send(anyString(), anyString(), anyString(), anyMap())).thenThrow(new IllegalStateException("failed"));
		assertThatCode(() -> create(NotificationType.WARNING)).doesNotThrowAnyException();
		assertThat(count()).isEqualTo(1);
		verify(sender).send(eq("active-token"), anyString(), anyString(), anyMap());
		verifyNoMoreInteractions(sender);
	}

	private long create(NotificationType type) {
		return notifications.create(USER, type, "title", "body", "456", true);
	}

	private long count() {
		return jdbc.sql("SELECT COUNT(*) FROM notifications WHERE user_id = :id").param("id", USER).query(Long.class).single();
	}

	private void device(String token, boolean active) {
		jdbc.sql("""
				INSERT INTO push_devices(user_id, installation_id, fcm_token, platform, active, last_seen_at)
				VALUES (:user, :installation, :token, 'ANDROID', :active, CURRENT_TIMESTAMP)
				""").param("user", USER).param("installation", UUID.randomUUID().toString())
				.param("token", token).param("active", active).update();
	}
}
