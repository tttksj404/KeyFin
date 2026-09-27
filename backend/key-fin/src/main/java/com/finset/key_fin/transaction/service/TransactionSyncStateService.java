package com.finset.key_fin.transaction.service;

import com.finset.key_fin.transaction.entity.TransactionAssetType;
import com.finset.key_fin.transaction.entity.TransactionSyncState;
import com.finset.key_fin.transaction.repository.TransactionSyncStateRepository;
import com.finset.key_fin.user.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Objects;

@Service
@RequiredArgsConstructor
public class TransactionSyncStateService {

	private final TransactionSyncStateRepository syncStateRepository;

	@Transactional(readOnly = true)
	public LocalDate calculateSyncStartDate(
			long userId,
			TransactionAssetType assetType,
			long assetId,
			LocalDate today
	) {
		Objects.requireNonNull(assetType, "assetType must not be null");
		Objects.requireNonNull(today, "today must not be null");
		return syncStateRepository
				.findByUserIdAndAssetTypeAndAssetId(userId, assetType, assetId)
				.map(TransactionSyncState::getLastSyncedAt)
				.map(LocalDateTime::toLocalDate)
				.map(lastSyncedDate -> lastSyncedDate.minusDays(1))
				.orElseGet(() -> today.minusDays(1));
	}

	@Transactional
	public void recordSyncSuccess(
			User user,
			TransactionAssetType assetType,
			long assetId,
		LocalDateTime syncedAt
	) {
		Objects.requireNonNull(user, "user must not be null");
		Objects.requireNonNull(assetType, "assetType must not be null");
		Objects.requireNonNull(syncedAt, "syncedAt must not be null");
		TransactionSyncState state = syncStateRepository
				.findByUserIdAndAssetTypeAndAssetId(user.getId(), assetType, assetId)
				.orElseGet(() -> TransactionSyncState.create(user, assetType, assetId));
		state.recordSyncSuccess(syncedAt);
		syncStateRepository.save(state);
	}

}

