package com.finset.key_fin.transaction.repository;

import com.finset.key_fin.transaction.entity.TransactionAssetType;
import com.finset.key_fin.transaction.entity.TransactionSyncState;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface TransactionSyncStateRepository extends JpaRepository<TransactionSyncState, Long> {

	Optional<TransactionSyncState> findByUserIdAndAssetTypeAndAssetId(
			Long userId,
			TransactionAssetType assetType,
			Long assetId
	);
}

