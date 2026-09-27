package com.finset.key_fin.notification.repository;

import java.sql.Types;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import com.finset.key_fin.notification.entity.InboxNotification;
import com.finset.key_fin.notification.entity.NotificationType;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.stereotype.Repository;

@Repository
@RequiredArgsConstructor
public class NotificationRepository {
	private final JdbcClient jdbc;
	private static final RowMapper<InboxNotification> ROW = (rs, index) -> new InboxNotification(
			rs.getLong("id"), NotificationType.valueOf(rs.getString("noti_type")),
			rs.getString("title"), rs.getString("body"), rs.getString("ref_id"),
			rs.getBoolean("requires_action"), rs.getBoolean("is_read"),
			rs.getTimestamp("created_at").toLocalDateTime());

	public boolean isActiveUser(long userId) {
		return jdbc.sql("SELECT COUNT(*) FROM users WHERE id = :userId AND deleted_at IS NULL")
				.param("userId", userId).query(Long.class).single() > 0;
	}

	public long insert(long userId, NotificationType type, String title, String body, String refId,
			boolean requiresAction, LocalDateTime now) {
		var key = new GeneratedKeyHolder();
		jdbc.sql("""
				INSERT INTO notifications (user_id, noti_type, title, body, ref_id, requires_action, is_read, created_at)
				VALUES (:userId, :type, :title, :body, :refId, :requiresAction, FALSE, :now)
				""").param("userId", userId).param("type", type.name()).param("title", title)
				.param("body", body, Types.LONGVARCHAR).param("refId", refId, Types.VARCHAR)
				.param("requiresAction", requiresAction).param("now", now).update(key, "id");
		return Objects.requireNonNull(key.getKey(), "Notification insert did not return an ID").longValue();
	}

	public List<InboxNotification> findPage(long userId, boolean unreadOnly, Long cursor, int limit) {
		String index = unreadOnly ? "idx_noti_user_read_id" : "idx_noti_user_id";
		String sql = """
				SELECT n.id, n.noti_type, n.title, n.body, n.ref_id, n.requires_action, n.is_read, n.created_at
				FROM notifications n FORCE INDEX (%s) JOIN users u ON u.id = n.user_id
				WHERE n.user_id = :userId AND u.deleted_at IS NULL
				""".formatted(index);
		if (unreadOnly) sql += " AND n.is_read = FALSE";
		if (cursor != null) sql += " AND n.id < :cursor";
		var query = jdbc.sql(sql + " ORDER BY n.id DESC LIMIT :limit")
				.param("userId", userId).param("limit", limit);
		if (cursor != null) query = query.param("cursor", cursor);
		return query.query(ROW).list();
	}

	public int markRead(long userId, long notificationId) {
		return jdbc.sql("""
				UPDATE notifications n JOIN users u ON u.id = n.user_id SET n.is_read = TRUE
				WHERE n.id = :id AND n.user_id = :userId AND u.deleted_at IS NULL AND n.is_read = FALSE
				""").param("id", notificationId).param("userId", userId).update();
	}

	public boolean existsOwned(long userId, long notificationId) {
		return jdbc.sql("""
				SELECT COUNT(*) FROM notifications n JOIN users u ON u.id = n.user_id
				WHERE n.id = :id AND n.user_id = :userId AND u.deleted_at IS NULL
				""").param("id", notificationId).param("userId", userId).query(Long.class).single() > 0;
	}
}
