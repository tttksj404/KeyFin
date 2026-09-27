package com.finset.key_fin.notification.repository;

import java.time.LocalDateTime;
import java.util.List;
import com.finset.key_fin.notification.entity.PushDevice;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
@RequiredArgsConstructor
public class PushDeviceRepository {
	private final JdbcClient jdbc;
	private static final RowMapper<PushDevice> ROW = (rs, index) -> new PushDevice(
			rs.getLong("id"), rs.getLong("user_id"), rs.getString("installation_id"),
			rs.getString("fcm_token"), rs.getString("platform"), rs.getBoolean("active"),
			rs.getTimestamp("last_seen_at").toLocalDateTime());

	public boolean isActiveUser(long userId) {
		return jdbc.sql("SELECT COUNT(*) FROM users WHERE id = :userId AND deleted_at IS NULL")
				.param("userId", userId).query(Long.class).single() > 0;
	}

	public List<PushDevice> lockRegistration(String installationId, String token) {
		return jdbc.sql("""
				SELECT * FROM push_devices WHERE installation_id = :installationId OR fcm_token = :token
				ORDER BY id FOR UPDATE
				""").param("installationId", installationId).param("token", token).query(ROW).list();
	}

	public void release(long id, LocalDateTime now) {
		jdbc.sql("UPDATE push_devices SET active = FALSE, fcm_token = NULL, updated_at = :now WHERE id = :id")
				.param("id", id).param("now", now).update();
	}

	public void insert(long userId, String installationId, String token, String platform, LocalDateTime now) {
		jdbc.sql("""
				INSERT INTO push_devices (user_id, installation_id, fcm_token, platform, active, last_seen_at, created_at, updated_at)
				VALUES (:userId, :installationId, :token, :platform, TRUE, :now, :now, :now)
				""").param("userId", userId).param("installationId", installationId)
				.param("token", token).param("platform", platform).param("now", now).update();
	}

	public void update(long id, long userId, String token, String platform, LocalDateTime now) {
		jdbc.sql("""
				UPDATE push_devices SET user_id = :userId, fcm_token = :token, platform = :platform,
				active = TRUE, last_seen_at = :now, updated_at = :now WHERE id = :id
				""").param("id", id).param("userId", userId).param("token", token)
				.param("platform", platform).param("now", now).update();
	}

	public void disconnect(long userId, String installationId, LocalDateTime now) {
		jdbc.sql("""
				UPDATE push_devices SET active = FALSE, fcm_token = NULL, updated_at = :now
				WHERE installation_id = :installationId AND user_id = :userId
				""").param("installationId", installationId).param("userId", userId).param("now", now).update();
	}

	public List<PushDevice> findActiveByUserId(long userId) {
		return jdbc.sql("""
				SELECT p.* FROM push_devices p JOIN users u ON u.id = p.user_id
				WHERE p.user_id = :userId AND p.active = TRUE AND p.fcm_token IS NOT NULL
				AND u.deleted_at IS NULL ORDER BY p.id
				""").param("userId", userId).query(ROW).list();
	}
}
