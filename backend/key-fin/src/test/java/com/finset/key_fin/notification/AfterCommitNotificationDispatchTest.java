package com.finset.key_fin.notification;

import java.util.Map;
import java.util.UUID;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.finset.key_fin.payment.event.TransferProposed;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.transaction.event.PendingTransactionSaved;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AfterCommitNotificationDispatchTest extends SpringIntegrationTestSupport {
	private static final long USER = 71002;
	@Autowired ApplicationEventPublisher events;
	@Autowired JdbcClient jdbc;
	@Autowired PlatformTransactionManager transactionManager;

	@BeforeEach
	void setup() {
		cleanup();
		jdbc.sql("INSERT INTO users(id,email,password,name) VALUES (:id,'after-commit@test.invalid','test','A')")
				.param("id", USER).update();
		jdbc.sql("INSERT INTO user_settings(user_id) VALUES (:id)").param("id", USER).update();
		jdbc.sql("""
				INSERT INTO push_devices(user_id, installation_id, fcm_token, platform, active, last_seen_at)
				VALUES (:user, :installation, 'active-token', 'ANDROID', TRUE, CURRENT_TIMESTAMP)
				""").param("user", USER).param("installation", UUID.randomUUID().toString()).update();
	}

	@AfterEach
	void cleanup() {
		for (String table : new String[]{"notifications", "push_devices", "user_settings"}) {
			jdbc.sql("DELETE FROM " + table + " WHERE user_id = :id").param("id", USER).update();
		}
		jdbc.sql("DELETE FROM users WHERE id = :id").param("id", USER).update();
	}

	@Test
	void pendingTransactionCommitStoresInboxAndDispatchesPush() throws Exception {
		new TransactionTemplate(transactionManager).executeWithoutResult(status ->
				events.publishEvent(new PendingTransactionSaved(USER, 1L, "GS25", 1_300)));

		assertThat(count("COACHING")).isEqualTo(1);
		verify(sender).send(eq("active-token"), eq("새로 정리할 거래가 있어요"), anyString(),
				argThat((Map<String, String> data) -> "COACHING".equals(data.get("type")) && "1".equals(data.get("refId"))));
		verifyNoMoreInteractions(sender);
	}

	@Test
	void transferProposedCommitStoresInboxAndDispatchesPush() throws Exception {
		new TransactionTemplate(transactionManager).executeWithoutResult(status ->
				events.publishEvent(new TransferProposed(USER, 5L)));

		assertThat(count("TRANSFER_REQUEST")).isEqualTo(1);
		verify(sender).send(eq("active-token"), eq("자동이체 준비 승인 필요"), anyString(),
				argThat((Map<String, String> data) -> "TRANSFER_REQUEST".equals(data.get("type")) && "5".equals(data.get("refId"))));
		verifyNoMoreInteractions(sender);
	}

	private long count(String type) {
		return jdbc.sql("SELECT COUNT(*) FROM notifications WHERE user_id = :id AND noti_type = :type")
				.param("id", USER).param("type", type).query(Long.class).single();
	}
}
