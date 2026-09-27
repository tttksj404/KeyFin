package com.finset.key_fin.notification;

import java.time.Instant;
import java.time.LocalDateTime;
import java.util.UUID;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import com.finset.key_fin.notification.dto.request.PushDeviceRequest;
import com.finset.key_fin.notification.service.PushDeviceService;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import static org.assertj.core.api.Assertions.*;

class PushDeviceIntegrationTest extends SpringIntegrationTestSupport {
    private static final long A = 901;
    private static final long B = 902;
    @Autowired JdbcClient jdbc;
    @Autowired PushDeviceService service;
    UUID installation;

    @BeforeEach void reset() {
        testClock.set(Instant.parse("2026-09-16T00:00:00Z"));
        cleanup();
        jdbc.sql("INSERT INTO users (id,email,password,name) VALUES (901,'push-a@test.invalid','test','A'),(902,'push-b@test.invalid','test','B')").update();
        installation = UUID.randomUUID();
    }

    @AfterEach void cleanup() {
        jdbc.sql("DELETE FROM push_devices WHERE user_id IN (901,902)").update();
        jdbc.sql("DELETE FROM users WHERE id IN (901,902)").update();
    }

    void register(long user, UUID id, String token) { service.register(user, id, new PushDeviceRequest(token, "ANDROID")); }
    long count() { return jdbc.sql("SELECT COUNT(*) FROM push_devices WHERE user_id IN (901,902)").query(Long.class).single(); }

    @Test void repeatedRegistrationAndRotationReuseRowWithKstClock() {
        register(A, installation, "first");
        long id = service.findActive(A).getFirst().id();
        register(A, installation, "first");
        register(A, installation, "rotated");
        assertThat(count()).isEqualTo(1);
        var device = service.findActive(A).getFirst();
        assertThat(device.id()).isEqualTo(id);
        assertThat(device.fcmToken()).isEqualTo("rotated");
        assertThat(device.lastSeenAt()).isEqualTo(LocalDateTime.of(2026,9,16,9,0));
    }

    @Test void ownershipChangesAndLatePreviousOwnerDeleteDoesNothing() {
        register(A, installation, "token");
        register(B, installation, "token");
        service.disconnect(A, installation);
        assertThat(service.findActive(A)).isEmpty();
        assertThat(service.findActive(B)).hasSize(1);
        assertThat(count()).isEqualTo(1);
        service.disconnect(B, installation);
        service.disconnect(B, installation);
        service.disconnect(B, UUID.randomUUID());
        assertThat(service.findActive(B)).isEmpty();
        assertThat(jdbc.sql("SELECT COUNT(*) FROM push_devices WHERE user_id IN (901,902) AND fcm_token IS NULL").query(Long.class).single()).isEqualTo(1);
        register(A, installation, "new");
        assertThat(count()).isEqualTo(1);
    }

    @Test void multipleDevicesCaseSensitiveTokensAndMaximumLengthAreSupported() {
        register(A, installation, "Case");
        register(A, UUID.randomUUID(), "case");
        register(A, UUID.randomUUID(), "x".repeat(2048));
        assertThat(service.findActive(A)).hasSize(3);
    }

    @Test void duplicateTokenIsReleasedBeforeReassignmentAndNullsAreNotUnique() {
        UUID second = UUID.randomUUID();
        UUID third = UUID.randomUUID();
        register(A, installation, "shared");
        register(B, second, "shared");
        register(A, third, "shared");
        assertThat(count()).isEqualTo(3);
        assertThat(service.findActive(A)).hasSize(1);
        assertThat(service.findActive(B)).isEmpty();
        assertThat(jdbc.sql("SELECT COUNT(*) FROM push_devices WHERE user_id IN (901,902) AND active = FALSE AND fcm_token IS NULL")
                .query(Long.class).single()).isEqualTo(2);
    }

    @Test void concurrentSameInstallationNeverCreatesDuplicates() throws Exception {
        concurrent(() -> register(A, installation, "one"), () -> register(B, installation, "two"));
        assertThat(count()).isEqualTo(1);
        assertThat(service.findActive(A).size() + service.findActive(B).size()).isEqualTo(1);
    }

    @Test void concurrentSameTokenHasExactlyOneActiveOwner() throws Exception {
        concurrent(() -> register(A, installation, "same"), () -> register(B, UUID.randomUUID(), "same"));
        assertThat(service.findActive(A).size() + service.findActive(B).size()).isEqualTo(1);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM push_devices WHERE fcm_token='same'").query(Long.class).single()).isEqualTo(1);
    }

    @Test void deletedUsersCannotRegisterOrReceive() {
        register(A, installation, "token");
        jdbc.sql("UPDATE users SET deleted_at = CURRENT_TIMESTAMP WHERE id=901").update();
        assertThat(service.findActive(A)).isEmpty();
        assertThatThrownBy(() -> register(A, installation, "other")).isInstanceOf(com.finset.key_fin.global.exception.BusinessException.class);
    }

    private void concurrent(Runnable first, Runnable second) throws Exception {
        var start = new CyclicBarrier(2);
        try (var executor = Executors.newFixedThreadPool(2)) {
            Future<?> a = executor.submit(() -> { await(start); first.run(); });
            Future<?> b = executor.submit(() -> { await(start); second.run(); });
            a.get(20, TimeUnit.SECONDS);
            b.get(20, TimeUnit.SECONDS);
        }
    }
    private static void await(CyclicBarrier barrier) {
        try { barrier.await(5, TimeUnit.SECONDS); }
        catch (Exception e) { throw new RuntimeException(e); }
    }
}
