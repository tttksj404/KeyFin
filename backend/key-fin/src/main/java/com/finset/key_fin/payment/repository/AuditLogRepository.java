package com.finset.key_fin.payment.repository;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import com.finset.key_fin.payment.entity.AuditLog;

public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {

	List<AuditLog> findAllByTargetTypeAndTargetIdOrderByIdAsc(String targetType, String targetId);
}
