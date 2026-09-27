package com.finset.key_fin.transaction.scheduler;

import com.finset.key_fin.transaction.service.TransactionSyncManager;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

@Slf4j
@Component
@RequiredArgsConstructor
public class TransactionSyncScheduler {

	private static final ZoneId SERVICE_ZONE = ZoneId.of("Asia/Seoul");

	private final UserRepository userRepository;
	private final TransactionSyncManager syncManager;
	private final AtomicBoolean running = new AtomicBoolean(false);

	@Scheduled(cron = "${transaction.sync.cron}", zone = "Asia/Seoul")
	public void syncAll() {
		if (!running.compareAndSet(false, true)) {
			log.warn("거래 동기화 건너뜀 — 이전 실행 진행 중");
			return;
		}

		try {
			LocalDateTime syncTime = LocalDateTime.now(SERVICE_ZONE);
			List<User> users = userRepository.findAllByFinUserKeyIsNotNullAndDeletedAtIsNull();
			int failed = 0;
			for (User user : users) {
				if (!syncUser(user.getId(), syncTime)) {
					failed++;
				}
			}
			log.info("거래 동기화 완료: users={}, failed={}", users.size(), failed);
		} finally {
			running.set(false);
		}
	}

	boolean syncUser(long userId, LocalDateTime syncTime) {
		try {
			syncManager.syncUser(userId, syncTime);
			return true;
		} catch (RuntimeException exception) {
			log.warn("거래 동기화 실패 — 다음 사용자로 진행: userId={}, cause={}", userId, exception.toString());
			return false;
		}
	}
}

