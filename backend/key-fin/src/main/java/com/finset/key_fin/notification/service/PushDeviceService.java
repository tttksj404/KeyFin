package com.finset.key_fin.notification.service;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.notification.dto.request.PushDeviceRequest;
import com.finset.key_fin.notification.entity.PushDevice;
import com.finset.key_fin.notification.exception.PushErrorCode;
import com.finset.key_fin.notification.repository.PushDeviceRepository;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class PushDeviceService {
	private final PushDeviceRepository repository;
	private final Clock clock;
	private final TransactionTemplate transaction;

	public PushDeviceService(PushDeviceRepository repository, Clock clock, PlatformTransactionManager manager) {
		this.repository = repository;
		this.clock = clock;
		this.transaction = new TransactionTemplate(manager);
		transaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
	}

	public void register(long userId, UUID installationId, PushDeviceRequest request) {
		withRetry(() -> {
			if (!repository.isActiveUser(userId)) throw new BusinessException(UserErrorCode.USER_NOT_FOUND);
			String installation = installationId.toString();
			List<PushDevice> rows = repository.lockRegistration(installation, request.token());
			LocalDateTime now = LocalDateTime.now(clock);
			PushDevice current = null;
			for (PushDevice row : rows) {
				if (row.installationId().equals(installation)) current = row;
				else repository.release(row.id(), now);
			}
			if (current == null) repository.insert(userId, installation, request.token(), request.platform(), now);
			else repository.update(current.id(), userId, request.token(), request.platform(), now);
		});
	}

	public void disconnect(long userId, UUID installationId) {
		withRetry(() -> repository.disconnect(userId, installationId.toString(), LocalDateTime.now(clock)));
	}

	public List<PushDevice> findActive(long userId) {
		return repository.findActiveByUserId(userId);
	}

	private void withRetry(Runnable action) {
		for (int attempt = 0; attempt < 3; attempt++) {
			try {
				transaction.executeWithoutResult(status -> action.run());
				return;
			} catch (DuplicateKeyException | PessimisticLockingFailureException ignored) {
				// 롤백된 트랜잭션을 재사용하지 않는다. SQL 예외에는 토큰이 포함될 수 있어 기록하지 않는다.
			}
		}
		throw new BusinessException(PushErrorCode.REGISTRATION_CONFLICT);
	}
}
