package com.finset.key_fin.transaction.repository;

import jakarta.persistence.EntityManager;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class SubcategoryQueryRepository {

	private final EntityManager entityManager;

	public Optional<Integer> findEnvelopeId(int subcategoryId) {
		@SuppressWarnings("unchecked")
		List<Object> rows = entityManager
				.createNativeQuery("SELECT envelope_id FROM subcategories WHERE id = :subcategoryId")
				.setParameter("subcategoryId", subcategoryId)
				.setMaxResults(1)
				.getResultList();
		return rows.stream().findFirst().map(value -> ((Number) value).intValue());
	}

	public List<SubcategoryQueryRow> findAllWithEnvelope() {
		@SuppressWarnings("unchecked")
		List<Object[]> rows = entityManager.createNativeQuery("""
				SELECT e.id,
				       e.name,
				       s.id,
				       s.name
				  FROM envelopes e
				  JOIN subcategories s ON s.envelope_id = e.id
				 ORDER BY e.id, s.id
				""").getResultList();

		return rows.stream()
				.map(row -> new SubcategoryQueryRow(
						((Number) row[0]).intValue(),
						(String) row[1],
						((Number) row[2]).intValue(),
						(String) row[3]
				))
				.toList();
	}
}
