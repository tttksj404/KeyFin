package com.finset.key_fin.transaction.repository;

import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import jakarta.persistence.EntityManager;
import jakarta.persistence.Query;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.sql.Date;
import java.sql.Time;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;

@Repository
@RequiredArgsConstructor
public class TransactionQueryRepository {

	private static final String BASE_QUERY = """
			SELECT t.id,
			       t.tx_type,
			       COALESCE(m.name, t.merchant_name_raw) AS merchant_name,
			       t.amount,
			       t.tx_date,
			       t.tx_time,
			       s.envelope_id,
			       t.subcategory_id,
			       s.name AS subcategory_name,
			       t.confirm_status,
			       t.exclude_tag,
			       t.status,
			       t.memo,
			       t.account_id,
			       t.card_id,
			       t.adjusted_amount
			  FROM transactions t
			  LEFT JOIN merchants m ON m.id = t.merchant_id
			  LEFT JOIN subcategories s ON s.id = t.subcategory_id
			 WHERE t.user_id = :userId
			   AND t.tx_date >= :startDate
			   AND t.tx_date < :endDate
			""";

	private final EntityManager entityManager;

	public List<TransactionQueryRow> findTransactions(TransactionSearchCondition condition) {
		StringBuilder sql = new StringBuilder(BASE_QUERY);
		if (condition.envelopeId() != null) {
			sql.append(" AND s.envelope_id = :envelopeId");
		}
		if (condition.subcategoryId() != null) {
			sql.append(" AND t.subcategory_id = :subcategoryId");
		}
		if (condition.accountId() != null) {
			sql.append(" AND t.account_id = :accountId");
		}
		if (condition.cardId() != null) {
			sql.append(" AND t.card_id = :cardId");
		}
		if (condition.cursor() != null) {
			sql.append("""
					 AND (t.tx_date, t.tx_time, t.id) < (
					       SELECT cursor_tx.tx_date, cursor_tx.tx_time, cursor_tx.id
					         FROM transactions cursor_tx
					        WHERE cursor_tx.id = :cursor
					          AND cursor_tx.user_id = :userId
					 )
					""");
		}
		sql.append(" ORDER BY t.tx_date DESC, t.tx_time DESC, t.id DESC");

		Query query = entityManager.createNativeQuery(sql.toString());
		query.setParameter("userId", condition.userId());
		query.setParameter("startDate", condition.startDate());
		query.setParameter("endDate", condition.endDate());
		setOptionalParameters(query, condition);
		query.setMaxResults(condition.limit());

		@SuppressWarnings("unchecked")
		List<Object[]> rows = query.getResultList();
		return rows.stream().map(this::mapRow).toList();
	}

	public List<TransactionQueryRow> findPendingTransactions(long userId, Long cursor, int limit) {
		StringBuilder sql = new StringBuilder("""
				SELECT t.id,
				       t.tx_type,
				       COALESCE(m.name, t.merchant_name_raw) AS merchant_name,
				       t.amount,
				       t.tx_date,
				       t.tx_time,
				       s.envelope_id,
				       t.subcategory_id,
				       s.name AS subcategory_name,
				       t.confirm_status,
				       t.exclude_tag,
				       t.status,
				       t.memo,
				       t.account_id,
				       t.card_id,
				       t.adjusted_amount
				  FROM transactions t
				  LEFT JOIN merchants m ON m.id = t.merchant_id
				  LEFT JOIN subcategories s ON s.id = t.subcategory_id
				 WHERE t.user_id = :userId
				   AND t.confirm_status = 'PENDING'
				   AND t.status = 'NORMAL'
				   AND t.tx_type <> 'DEPOSIT'
				""");
		if (cursor != null) {
			sql.append("""
					 AND (t.tx_date, t.tx_time, t.id) < (
					       SELECT cursor_tx.tx_date, cursor_tx.tx_time, cursor_tx.id
					         FROM transactions cursor_tx
					        WHERE cursor_tx.id = :cursor
					          AND cursor_tx.user_id = :userId
					 )
					""");
		}
		sql.append(" ORDER BY t.tx_date DESC, t.tx_time DESC, t.id DESC");

		Query query = entityManager.createNativeQuery(sql.toString());
		query.setParameter("userId", userId);
		if (cursor != null) {
			query.setParameter("cursor", cursor);
		}
		query.setMaxResults(limit);

		@SuppressWarnings("unchecked")
		List<Object[]> rows = query.getResultList();
		return rows.stream().map(this::mapRow).toList();
	}

	public boolean existsSubcategory(int subcategoryId) {
		Number count = (Number) entityManager.createNativeQuery(
				"SELECT COUNT(*) FROM subcategories WHERE id = :subcategoryId"
		).setParameter("subcategoryId", subcategoryId).getSingleResult();
		return count.longValue() > 0;
	}

	private void setOptionalParameters(Query query, TransactionSearchCondition condition) {
		if (condition.envelopeId() != null) {
			query.setParameter("envelopeId", condition.envelopeId());
		}
		if (condition.subcategoryId() != null) {
			query.setParameter("subcategoryId", condition.subcategoryId());
		}
		if (condition.accountId() != null) {
			query.setParameter("accountId", condition.accountId());
		}
		if (condition.cardId() != null) {
			query.setParameter("cardId", condition.cardId());
		}
		if (condition.cursor() != null) {
			query.setParameter("cursor", condition.cursor());
		}
	}

	private TransactionQueryRow mapRow(Object[] row) {
		return new TransactionQueryRow(
				longValue(row[0]),
				TransactionType.valueOf((String) row[1]),
				(String) row[2],
				longValue(row[3]),
				localDate(row[4]),
				localTime(row[5]),
				integerValue(row[6]),
				integerValue(row[7]),
				(String) row[8],
				ConfirmStatus.valueOf((String) row[9]),
				ExcludeTag.valueOf((String) row[10]),
				TransactionStatus.valueOf((String) row[11]),
				(String) row[12],
				longValue(row[13]),
				longValue(row[14]),
				longValue(row[15])
		);
	}

	private static Long longValue(Object value) {
		return value == null ? null : ((Number) value).longValue();
	}

	private static Integer integerValue(Object value) {
		return value == null ? null : ((Number) value).intValue();
	}

	private static LocalDate localDate(Object value) {
		if (value instanceof LocalDate localDate) {
			return localDate;
		}
		return ((Date) value).toLocalDate();
	}

	private static LocalTime localTime(Object value) {
		if (value instanceof LocalTime localTime) {
			return localTime;
		}
		return ((Time) value).toLocalTime();
	}
}
