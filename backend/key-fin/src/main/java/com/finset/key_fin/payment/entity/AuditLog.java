package com.finset.key_fin.payment.entity;

import com.finset.key_fin.global.base.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "audit_logs")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AuditLog extends BaseEntity {

	public static final String TARGET_PREPARE_TRANSFER = "PREPARE_TRANSFER";

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "user_id", nullable = false)
	private Long userId;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 20)
	private AuditAction action;

	@Column(name = "target_type", nullable = false, length = 30)
	private String targetType;

	@Column(name = "target_id", nullable = false, length = 30)
	private String targetId;

	@Column(columnDefinition = "TEXT")
	private String basis;

	public static AuditLog transfer(long userId, AuditAction action, long transferId, String basis) {
		AuditLog log = new AuditLog();
		log.userId = userId;
		log.action = action;
		log.targetType = TARGET_PREPARE_TRANSFER;
		log.targetId = String.valueOf(transferId);
		log.basis = basis;
		return log;
	}

	public enum AuditAction {
		EXECUTE,
		HOLD,
		FAIL,
		CANCEL
	}
}
