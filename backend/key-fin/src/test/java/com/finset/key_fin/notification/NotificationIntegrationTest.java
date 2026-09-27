package com.finset.key_fin.notification;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.finset.key_fin.notification.dto.response.NotificationResponse;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.exception.NotificationErrorCode;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationContext;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.test.web.servlet.MockMvc;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.when;
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class NotificationIntegrationTest extends SpringIntegrationTestSupport {
	private static final long USER = 70001;
	private static final long OTHER = 70002;
	private static final long DELETED = 70003;
	@Autowired NotificationService service;
	@Autowired JdbcClient jdbc;
	@Autowired PlatformTransactionManager transactionManager;
	@Autowired MockMvc mvc;
	@Autowired JwtTokenProvider jwt;
	@Autowired ApplicationContext context;

	@BeforeEach
	void fixture() {
		testClock.set(Instant.parse("2026-09-16T13:00:00.987Z"));
		cleanup();
		jdbc.sql("""
				INSERT INTO users(id,email,password,name,deleted_at) VALUES
				(70001,'notification-a@test.invalid','test','A',NULL),
				(70002,'notification-b@test.invalid','test','B',NULL),
				(70003,'notification-deleted@test.invalid','test','D',CURRENT_TIMESTAMP)
				""").update();
	}

	@AfterEach
	void cleanup() {
		jdbc.sql("DELETE FROM notifications WHERE user_id IN (70001,70002,70003)").update();
		jdbc.sql("DELETE FROM users WHERE id IN (70001,70002,70003)").update();
	}

	@Test
	void savesAllFieldsAndNullableFieldsWithKstClockWithoutReadingOnList() {
		long id = service.create(USER, NotificationType.TRANSFER_REQUEST, "이체 승인 요청", "본문", "456", true);
		var row = service.list(USER, false, null, null).items().getFirst();
		assertThat(row).isEqualTo(new NotificationResponse(id, NotificationType.TRANSFER_REQUEST,
				"이체 승인 요청", "본문", "456", true, false, LocalDateTime.of(2026, 9, 16, 22, 0)));
		assertThat(service.list(USER, true, null, null).items()).containsExactly(row);
		long nullable = create(USER);
		var first = service.list(USER, false, null, null).items().getFirst();
		assertThat(first.id()).isEqualTo(nullable);
		assertThat(first.body()).isNull();
		assertThat(first.refId()).isNull();
		assertThat(first.requiresAction()).isFalse();
	}

	@Test
	void storesUtf8mb4CharacterAndTextByteBoundaries() {
		String title = "😀".repeat(100);
		String ref = "😀".repeat(30);
		String body = "가".repeat(21_845); // 65,535 UTF-8 bytes, exactly the TEXT limit.
		service.create(USER, NotificationType.WARNING, title, body, ref, false);
		var row = service.list(USER, false, null, null).items().getFirst();
		assertThat(row.title()).isEqualTo(title);
		assertThat(row.refId()).isEqualTo(ref);
		assertThat(row.body()).isEqualTo(body);
		assertThat(service.list(USER, true, null, null).items()).containsExactly(row);
	}

	@Test
	void rejectsMissingAndDeletedRecipientsAndHidesDeletedUsersInbox() {
		for (long id : new long[]{DELETED, 79999}) {
			assertThatThrownBy(() -> create(id)).isInstanceOfSatisfying(BusinessException.class,
					e -> assertThat(e.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		}
		long id = create(USER);
		jdbc.sql("UPDATE users SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id").param("id", USER).update();
		assertThat(service.list(USER, false, null, null).items()).isEmpty();
		assertNotFound(() -> service.markRead(USER, id));
	}

	@Test
	void joinsCallerTransactionAndRollsBackNotification() {
		var tx = new TransactionTemplate(transactionManager);
		long id = tx.execute(status -> {
			long saved = create(USER);
			assertThat(service.list(USER, false, null, null).items()).extracting(NotificationResponse::id).contains(saved);
			status.setRollbackOnly();
			return saved;
		});
		assertThat(jdbc.sql("SELECT COUNT(*) FROM notifications WHERE id = :id").param("id", id).query(Long.class).single()).isZero();
	}

	@Test
	void isolatesUsersAndFiltersUnreadWithoutChangingActionState() {
		long unread = service.create(USER, NotificationType.TRANSFER_REQUEST, "승인", null, "999", true);
		long read = create(USER);
		create(OTHER);
		service.markRead(USER, read);
		service.markRead(USER, read);
		assertThat(service.list(USER, false, null, null).items()).extracting(NotificationResponse::id).containsExactly(read, unread);
		assertThat(service.list(USER, true, null, null).items()).extracting(NotificationResponse::id).containsExactly(unread);
		assertNotFound(() -> service.markRead(OTHER, unread));
		assertNotFound(() -> service.markRead(USER, Long.MAX_VALUE));
		service.markRead(USER, unread);
		var row = service.list(USER, false, null, null).items().getLast();
		assertThat(row.isRead()).isTrue();
		assertThat(row.requiresAction()).isTrue();
		assertThat(row.refId()).isEqualTo("999");
		assertThat(service.list(USER, true, null, null).items()).isEmpty();
	}

	@Test
	void paginatesSameTimestampAndHandlesNewRowsAndReadChangesBetweenPages() {
		long oldest = create(USER);
		long middle = create(USER);
		long latest = create(USER);
		var page = service.list(USER, true, null, 1);
		assertThat(page.items()).extracting(NotificationResponse::id).containsExactly(latest);
		assertThat(page.nextCursor()).isEqualTo(latest);
		create(USER); // Newly inserted rows belong to a new first-page fetch.
		service.markRead(USER, latest); // The cursor row need not remain unread.
		service.markRead(USER, middle);
		var next = service.list(USER, true, page.nextCursor(), 1);
		assertThat(next.items()).extracting(NotificationResponse::id).containsExactly(oldest);
		assertThat(next.nextCursor()).isNull();
		assertThat(service.list(USER, false, latest, 2).items())
				.extracting(NotificationResponse::id).containsExactly(middle, oldest);
		assertThat(service.list(USER, false, oldest, 2).items()).isEmpty();
		assertThat(service.list(USER, false, oldest, 2).nextCursor()).isNull();
	}

	@Test
	void handlesEmptyExactSizeAndDefaultSizePages() {
		assertThat(service.list(USER, false, null, null).items()).isEmpty();
		assertThat(service.list(USER, false, null, null).nextCursor()).isNull();
		for (int i = 0; i < 21; i++) create(USER);
		var first = service.list(USER, false, null, null);
		assertThat(first.items()).hasSize(20);
		assertThat(first.nextCursor()).isEqualTo(first.items().getLast().id());
		assertThat(service.list(USER, false, first.nextCursor(), null).items()).hasSize(1);
		assertThat(service.list(USER, false, null, 21).nextCursor()).isNull();
		assertThat(service.list(USER, false, null, 100).items()).hasSize(21);
	}

	@Test
	void migrationKeepsExistingIndexAndAddsBothPaginationIndexes() {
		List<String> indexes = jdbc.sql("""
				SELECT CONCAT(index_name, ':', GROUP_CONCAT(column_name ORDER BY seq_in_index))
				FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'notifications'
				GROUP BY index_name
				""").query(String.class).list();
		assertThat(indexes).contains("idx_noti_user:user_id,is_read,created_at", "idx_noti_user_id:user_id,id",
				"idx_noti_user_read_id:user_id,is_read,id");
	}

	@Test
	void authenticatedApiUsesSessionOwnerAndSerializesContractWithoutFirebase() throws Exception {
		long id = service.create(USER, NotificationType.TRANSFER_REQUEST, "이체 승인 요청", "본문", "456", true);
		create(OTHER);
		mvc.perform(get("/api/v1/notifications").header("Authorization", bearer(USER)))
				.andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.items.length()").value(1))
				.andExpect(jsonPath("$.data.items[0].id").value(id))
				.andExpect(jsonPath("$.data.items[0].type").value("TRANSFER_REQUEST"))
				.andExpect(jsonPath("$.data.items[0].title").value("이체 승인 요청"))
				.andExpect(jsonPath("$.data.items[0].body").value("본문"))
				.andExpect(jsonPath("$.data.items[0].refId").value("456"))
				.andExpect(jsonPath("$.data.items[0].requiresAction").value(true))
				.andExpect(jsonPath("$.data.items[0].isRead").value(false))
				.andExpect(jsonPath("$.data.items[0].read").doesNotExist())
				.andExpect(jsonPath("$.data.items[0].createdAt").value("2026-09-16T22:00:00"))
				.andExpect(jsonPath("$.data.nextCursor").value(nullValue()));
		for (int i = 0; i < 2; i++) {
			mvc.perform(patch("/api/v1/notifications/{id}/read", id).header("Authorization", bearer(USER)))
					.andExpect(status().isOk()).andExpect(jsonPath("$.data").value(nullValue()));
		}
		mvc.perform(get("/api/v1/notifications").param("unreadOnly", "true").header("Authorization", bearer(USER)))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.items").isEmpty());
	}

	@Test
	void apiExposesCursorAndUsesItOnTheNextPage() throws Exception {
		long older = create(USER);
		long newer = create(USER);
		mvc.perform(get("/api/v1/notifications").param("size", "1").header("Authorization", bearer(USER)))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.items[0].id").value(newer))
				.andExpect(jsonPath("$.data.nextCursor").value(newer));
		mvc.perform(get("/api/v1/notifications").param("size", "1").param("cursor", String.valueOf(newer))
				.header("Authorization", bearer(USER)))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.items[0].id").value(older))
				.andExpect(jsonPath("$.data.items[0].body").value(nullValue()))
				.andExpect(jsonPath("$.data.items[0].refId").value(nullValue()))
				.andExpect(jsonPath("$.data.nextCursor").value(nullValue()));
	}

	@Test
	void realSecurityFilterRejectsMissingAndInvalidAccessTokens() throws Exception {
		long id = create(USER);
		mvc.perform(get("/api/v1/notifications")).andExpect(status().isUnauthorized());
		mvc.perform(patch("/api/v1/notifications/{id}/read", id)).andExpect(status().isUnauthorized());
		for (String token : new String[]{"invalid", jwt.generateRefreshToken(USER)}) {
			mvc.perform(get("/api/v1/notifications").header("Authorization", "Bearer " + token))
					.andExpect(status().isUnauthorized());
			mvc.perform(patch("/api/v1/notifications/{id}/read", id).header("Authorization", "Bearer " + token))
					.andExpect(status().isUnauthorized());
		}
		assertThat(service.list(USER, true, null, null).items()).hasSize(1);
	}

	@Test
	void apiReturnsSameNotFoundForForeignAndAbsentNotifications() throws Exception {
		long foreign = create(OTHER);
		for (long id : new long[]{foreign, Long.MAX_VALUE}) {
			mvc.perform(patch("/api/v1/notifications/{id}/read", id).header("Authorization", bearer(USER)))
					.andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("NOTI_001"));
		}
		assertThat(service.list(OTHER, true, null, null).items()).hasSize(1);
	}

	@Test
	void apiRejectsInvalidQueryAndPathParameters() throws Exception {
		for (String[] query : new String[][]{
				{"cursor", "0"}, {"cursor", "-1"}, {"cursor", "abc"}, {"cursor", "9223372036854775808"},
				{"size", "0"}, {"size", "-1"}, {"size", "101"}, {"size", "abc"}, {"unreadOnly", "invalid"}}) {
			mvc.perform(get("/api/v1/notifications").param(query[0], query[1]).header("Authorization", bearer(USER)))
					.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_001"));
		}
		for (String id : new String[]{"0", "-1", "abc", "9223372036854775808"}) {
			mvc.perform(patch("/api/v1/notifications/{id}/read", id).header("Authorization", bearer(USER)))
					.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_001"));
		}
	}

	@Test
	void swaggerDescribesOnlyListAndIndividualReadWithActualResponseSchema() throws Exception {
		mvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.paths['/api/v1/notifications'].post").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/notifications'].get.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/notifications'].get.parameters[*].name")
						.value(containsInAnyOrder("unreadOnly", "cursor", "size")))
				.andExpect(jsonPath("$.paths['/api/v1/notifications'].get.responses['200'].content['application/json'].schema['$ref']")
						.value("#/components/schemas/BaseResponseNotificationListResponse"))
				.andExpect(jsonPath("$.components.schemas.NotificationListResponse.properties.items.items['$ref']")
						.value("#/components/schemas/NotificationResponse"))
				.andExpect(jsonPath("$.components.schemas.NotificationResponse.properties.isRead.type").value("boolean"))
				.andExpect(jsonPath("$.components.schemas.NotificationResponse.properties.read").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/notifications/{notificationId}/read'].patch.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/notifications/{notificationId}/read'].patch.requestBody").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/notifications/{notificationId}/read'].patch.responses['404'].description")
						.value("본인 소유 알림을 찾을 수 없음 (NOTI_001)"));
	}

	private String bearer(long userId) {
		return "Bearer " + jwt.generateAccessToken(userId);
	}

	private long create(long userId) {
		return service.create(userId, NotificationType.WARNING, "테스트", null, null, false);
	}

	private void assertNotFound(Runnable operation) {
		assertThatThrownBy(operation::run).isInstanceOfSatisfying(BusinessException.class,
				e -> assertThat(e.getErrorCode()).isEqualTo(NotificationErrorCode.NOTIFICATION_NOT_FOUND));
	}
}
