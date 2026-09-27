package com.finset.key_fin.transaction.repository;

import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.time.LocalTime;
import java.util.Collection;
import java.util.Optional;

public interface TransactionRepository extends JpaRepository<Transaction, Long> {

	Optional<Transaction> findByIdAndUserId(Long id, Long userId);

	List<Transaction> findAllByIdInAndUserId(Collection<Long> ids, Long userId);

	List<Transaction> findAllByUserIdOrderByTransactionDateAscTransactionTimeAscIdAsc(Long userId);

	long countByUserIdAndConfirmStatusAndStatusAndTransactionTypeNot(
			Long userId,
			ConfirmStatus confirmStatus,
			TransactionStatus status,
			TransactionType transactionType
	);

	@Query("""
			select t.user.id as userId, count(t.id) as pendingCount
			from Transaction t
			where t.confirmStatus = com.finset.key_fin.transaction.entity.ConfirmStatus.PENDING
			  and t.status = com.finset.key_fin.transaction.entity.TransactionStatus.NORMAL
			  and t.transactionType <> com.finset.key_fin.transaction.entity.TransactionType.DEPOSIT
			  and t.user.deletedAt is null
			group by t.user.id
			""")
	List<PendingTransactionSummary> findPendingTransactionSummaries();

	boolean existsByUserIdAndFinTransactionUniqueNo(Long userId, String finTransactionUniqueNo);

	Optional<Transaction> findByUserIdAndFinTransactionUniqueNo(Long userId, String finTransactionUniqueNo);

	Optional<Transaction> findFirstByUserIdAndAccountIdAndTransactionDateAndTransactionTimeAndAmountAndStatusAndExcludeTagNotAndConfirmStatusInOrderByIdDesc(
			Long userId,
			Long accountId,
			LocalDate transactionDate,
			LocalTime transactionTime,
			Long amount,
			TransactionStatus status,
			ExcludeTag excludeTag,
			Collection<ConfirmStatus> confirmStatuses
	);

	@Query("""
			select coalesce(sum(t.amount), 0) from Transaction t
			where t.cardId = :cardId
			  and t.source = com.finset.key_fin.transaction.entity.TransactionSource.LIVE
			  and t.transactionType = com.finset.key_fin.transaction.entity.TransactionType.CARD
			  and t.status = com.finset.key_fin.transaction.entity.TransactionStatus.NORMAL
			  and t.transactionDate between :from and :to
			""")
	long sumLiveCardApprovals(@Param("cardId") Long cardId, @Param("from") LocalDate from, @Param("to") LocalDate to);

	@Query("""
			select t from Transaction t
			where t.cardId = :cardId
			  and t.source = com.finset.key_fin.transaction.entity.TransactionSource.LIVE
			  and t.transactionType = com.finset.key_fin.transaction.entity.TransactionType.CARD
			  and t.status = com.finset.key_fin.transaction.entity.TransactionStatus.NORMAL
			  and t.transactionDate between :from and :to
			order by t.transactionDate desc, t.transactionTime desc, t.id desc
			""")
	List<Transaction> findLiveCardApprovals(@Param("cardId") Long cardId, @Param("from") LocalDate from, @Param("to") LocalDate to);
}
