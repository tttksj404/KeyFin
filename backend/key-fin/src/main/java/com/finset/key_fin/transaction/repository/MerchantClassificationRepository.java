package com.finset.key_fin.transaction.repository;

import jakarta.persistence.EntityManager;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class MerchantClassificationRepository {

	private final EntityManager entityManager;

	public Optional<MerchantClassification> findByFinanceMerchantId(long financeMerchantId) {
		@SuppressWarnings("unchecked")
		List<Object[]> rows = entityManager.createNativeQuery("""
				SELECT id, subcategory_id
				  FROM merchants
				 WHERE fin_merchant_id = :financeMerchantId
				""")
				.setParameter("financeMerchantId", financeMerchantId)
				.setMaxResults(1)
				.getResultList();

		return rows.stream()
				.findFirst()
				.map(row -> new MerchantClassification(
						((Number) row[0]).longValue(),
						((Number) row[1]).intValue()
				));
	}
}
