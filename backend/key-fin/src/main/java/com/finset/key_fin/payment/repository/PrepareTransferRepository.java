package com.finset.key_fin.payment.repository;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Limit;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.entity.TransferStatus;

public interface PrepareTransferRepository extends JpaRepository<PrepareTransfer, Long> {

	List<PrepareTransfer> findAllByUserIdOrderByIdDesc(Long userId);

	List<PrepareTransfer> findAllByUserIdAndStatusOrderByIdDesc(Long userId, TransferStatus status);

	@Query("""
			select t from PrepareTransfer t
			where t.userId = :userId
			  and (:status is null or t.status = :status)
			  and (:from is null or t.dueDate >= :from)
			  and (:to is null or t.dueDate < :to)
			  and (:cursor is null or t.id < :cursor)
			order by t.id desc
			""")
	List<PrepareTransfer> findPage(@Param("userId") Long userId, @Param("status") TransferStatus status,
			@Param("from") LocalDate from, @Param("to") LocalDate to, @Param("cursor") Long cursor, Limit limit);

	Optional<PrepareTransfer> findByIdAndUserId(Long id, Long userId);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("select t from PrepareTransfer t where t.id = :id and t.userId = :userId")
	Optional<PrepareTransfer> findByIdAndUserIdForUpdate(@Param("id") Long id, @Param("userId") Long userId);

	List<PrepareTransfer> findAllByStatus(TransferStatus status);

	@Query("""
			select coalesce(sum(t.requiredAmount), 0) from PrepareTransfer t
			where t.userId = :userId
			  and t.status = com.finset.key_fin.payment.entity.TransferStatus.EXECUTED
			  and t.executedAt >= :from and t.executedAt < :to
			""")
	long sumExecutedAmount(@Param("userId") Long userId, @Param("from") LocalDateTime from, @Param("to") LocalDateTime to);

	List<PrepareTransfer> findAllByStatusAndDueDateBefore(TransferStatus status, LocalDate date);
}
