package com.finset.key_fin.notification;

import java.sql.Connection;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import javax.sql.DataSource;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.entity.PushDevice;
import com.finset.key_fin.notification.repository.NotificationRepository;
import com.finset.key_fin.notification.repository.PushDeviceRepository;
import com.finset.key_fin.notification.service.*;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@SpringJUnitConfig(NotificationPushTransactionTest.Config.class)
class NotificationPushTransactionTest {
	@Autowired NotificationService notifications;
	@Autowired NotificationRepository repository;
	@Autowired UserSettingsRepository settings;
	@Autowired PushDeviceRepository devices;
	@Autowired FcmSender sender;
	@Autowired DataSource dataSource;
	@Autowired DataSourceTransactionManager manager;
	private final List<Connection> connections = new ArrayList<>();

	@BeforeEach
	void setup() throws Exception {
		reset(repository, settings, devices, sender, dataSource);
		when(dataSource.getConnection()).thenAnswer(invocation -> {
			Connection connection = mock(Connection.class);
			when(connection.getAutoCommit()).thenReturn(true);
			connections.add(connection);
			return connection;
		});
		when(repository.isActiveUser(1)).thenReturn(true);
		when(repository.insert(anyLong(), any(), anyString(), any(), any(), anyBoolean(), any())).thenReturn(123L);
		when(settings.findById(1L)).thenAnswer(invocation -> {
			assertThat(TransactionSynchronizationManager.isActualTransactionActive()).isTrue();
			assertThat(TransactionSynchronizationManager.isCurrentTransactionReadOnly()).isTrue();
			return Optional.of(NotificationPushPolicyTest.settings());
		});
		when(devices.findActiveByUserId(1)).thenReturn(List.of(new PushDevice(10, 1, "install", "token", "ANDROID", true, null)));
	}

	@Test
	void commitPrecedesNewReadTransactionAndFcmRunsWithoutDatabaseResources() throws Exception {
		when(sender.send(anyString(), anyString(), anyString(), anyMap())).thenAnswer(invocation -> {
			assertThat(connections).hasSize(2);
			for (Connection connection : connections) verify(connection).commit();
			assertThat(TransactionSynchronizationManager.isActualTransactionActive()).isFalse();
			assertThat(TransactionSynchronizationManager.hasResource(dataSource)).isFalse();
			return "accepted";
		});
		new TransactionTemplate(manager).executeWithoutResult(status -> {
			assertThat(create()).isEqualTo(123);
			assertThat(connections).hasSize(1);
			verifyNoInteractions(settings, devices, sender);
		});
		verify(sender).send(eq("token"), anyString(), anyString(), anyMap());
		verifyNoMoreInteractions(sender);
	}

	@Test
	void rollbackNeverLoadsSettingsOrSends() throws Exception {
		new TransactionTemplate(manager).executeWithoutResult(status -> {
			create();
			status.setRollbackOnly();
		});
		assertThat(connections).hasSize(1);
		verify(connections.getFirst()).rollback();
		verifyNoInteractions(settings, devices, sender);
	}

	@Test
	void directCallOpensItsOwnTransactionAndDispatchesAfterCommit() throws Exception {
		assertThat(create()).isEqualTo(123);
		assertThat(connections).hasSize(2);
		verify(connections.getFirst()).commit();
		verify(sender).send(eq("token"), anyString(), anyString(), anyMap());
	}

	@Test
	void postCommitReadFailureCannotChangeCreationResult() throws Exception {
		doThrow(new IllegalStateException("database unavailable")).when(settings).findById(1L);
		assertThat(create()).isEqualTo(123);
		verify(connections.getFirst()).commit();
		verify(connections.getLast()).rollback();
		verifyNoInteractions(sender);
	}

	private long create() {
		return notifications.create(1, NotificationType.COACHING, "title", "body", null, false);
	}

	@Configuration(proxyBeanMethods = false)
	@EnableTransactionManagement
	@Import({NotificationService.class, NotificationPushListener.class, NotificationPushRecipients.class, NotificationPushPolicy.class})
	static class Config {
		@Bean DataSource dataSource() { return mock(DataSource.class); }
		@Bean DataSourceTransactionManager transactionManager(DataSource dataSource) { return new DataSourceTransactionManager(dataSource); }
		@Bean NotificationRepository notificationRepository() { return mock(NotificationRepository.class); }
		@Bean UserSettingsRepository userSettingsRepository() { return mock(UserSettingsRepository.class); }
		@Bean PushDeviceRepository pushDeviceRepository() { return mock(PushDeviceRepository.class); }
		@Bean FcmSender fcmSender() { return mock(FcmSender.class); }
		@Bean Clock clock() { return Clock.fixed(Instant.parse("2026-09-18T00:00:00Z"), ZoneOffset.UTC); }
	}
}
