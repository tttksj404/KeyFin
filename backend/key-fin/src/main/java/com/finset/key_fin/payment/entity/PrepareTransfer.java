package com.finset.key_fin.payment.entity;

import java.time.LocalDate;
import java.time.LocalDateTime;
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
@Table(name = "prepare_transfers")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class PrepareTransfer extends BaseEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "user_id", nullable = false)
	private Long userId;

	@Column(name = "fixed_expense_id")
	private Long fixedExpenseId;

	@Column(name = "card_billing_id")
	private Long cardBillingId;

	@Column(name = "scheduled_date", nullable = false)
	private LocalDate scheduledDate;

	@Column(name = "due_date", nullable = false)
	private LocalDate dueDate;

	@Column(name = "required_amount", nullable = false)
	private long requiredAmount;

	@Column(name = "from_account_id", nullable = false)
	private Long fromAccountId;

	@Column(name = "to_account_id", nullable = false)
	private Long toAccountId;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 20)
	private TransferStatus status = TransferStatus.PROPOSED;

	@Column(name = "institution_tx_no", length = 20)
	private String institutionTxNo;

	@Column(name = "executed_at")
	private LocalDateTime executedAt;

	@Column(name = "fail_reason", length = 255)
	private String failReason;

	public static PrepareTransfer proposeForFixedExpense(long userId, long fixedExpenseId, LocalDate scheduledDate,
			LocalDate dueDate, long requiredAmount, long fromAccountId, long toAccountId) {
		PrepareTransfer transfer = base(userId, scheduledDate, dueDate, requiredAmount, fromAccountId, toAccountId);
		transfer.fixedExpenseId = fixedExpenseId;
		return transfer;
	}

	public static PrepareTransfer proposeForCardBilling(long userId, long cardBillingId, LocalDate scheduledDate,
			LocalDate dueDate, long requiredAmount, long fromAccountId, long toAccountId) {
		PrepareTransfer transfer = base(userId, scheduledDate, dueDate, requiredAmount, fromAccountId, toAccountId);
		transfer.cardBillingId = cardBillingId;
		return transfer;
	}

	private static PrepareTransfer base(long userId, LocalDate scheduledDate, LocalDate dueDate, long requiredAmount,
			long fromAccountId, long toAccountId) {
		if (requiredAmount <= 0) {
			throw new IllegalArgumentException("requiredAmount must be positive");
		}
		if (fromAccountId == toAccountId) {
			throw new IllegalArgumentException("from and to account must differ");
		}
		if (dueDate.isBefore(scheduledDate)) {
			throw new IllegalArgumentException("dueDate must not be before scheduledDate");
		}
		PrepareTransfer transfer = new PrepareTransfer();
		transfer.userId = userId;
		transfer.scheduledDate = scheduledDate;
		transfer.dueDate = dueDate;
		transfer.requiredAmount = requiredAmount;
		transfer.fromAccountId = fromAccountId;
		transfer.toAccountId = toAccountId;
		return transfer;
	}

	public boolean isProposed() {
		return status == TransferStatus.PROPOSED;
	}

	public boolean isApproved() {
		return status == TransferStatus.APPROVED;
	}

	public void updateRequiredAmount(long requiredAmount) {
		requireProposed();
		if (requiredAmount <= 0) {
			throw new IllegalArgumentException("requiredAmount must be positive");
		}
		this.requiredAmount = requiredAmount;
	}

	public void approve(String institutionTxNo) {
		requireProposed();
		if (institutionTxNo == null || institutionTxNo.isBlank()) {
			throw new IllegalArgumentException("institutionTxNo must not be blank");
		}
		this.institutionTxNo = institutionTxNo;
		this.status = TransferStatus.APPROVED;
	}

	public void markExecuted(LocalDateTime executedAt) {
		requireApproved();
		this.executedAt = executedAt;
		this.status = TransferStatus.EXECUTED;
	}

	public void markFailed(String reason) {
		requireApproved();
		this.failReason = reason;
		this.status = TransferStatus.FAILED;
	}

	public void cancel(String reason) {
		requireProposed();
		this.failReason = reason;
		this.status = TransferStatus.CANCELED;
	}

	public boolean isFailed() {
		return status == TransferStatus.FAILED;
	}

	/** 실패한 제안을 재사용 — 같은 출금 건은 유니크 키 때문에 새 행을 만들 수 없다. */
	public void reopen(LocalDate scheduledDate, long requiredAmount) {
		if (!isFailed()) {
			throw new IllegalStateException("transfer is not FAILED: " + status);
		}
		if (requiredAmount <= 0) {
			throw new IllegalArgumentException("requiredAmount must be positive");
		}
		this.scheduledDate = scheduledDate;
		this.requiredAmount = requiredAmount;
		this.institutionTxNo = null;
		this.failReason = null;
		this.status = TransferStatus.PROPOSED;
	}

	private void requireProposed() {
		if (status != TransferStatus.PROPOSED) {
			throw new IllegalStateException("transfer is not PROPOSED: " + status);
		}
	}

	private void requireApproved() {
		if (status != TransferStatus.APPROVED) {
			throw new IllegalStateException("transfer is not APPROVED: " + status);
		}
	}
}
