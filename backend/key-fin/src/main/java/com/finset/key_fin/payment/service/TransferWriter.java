package com.finset.key_fin.payment.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult;
import com.finset.key_fin.payment.dto.response.TransferApproveResponse;
import com.finset.key_fin.payment.entity.AuditLog;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.event.TransferCompleted;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.repository.AuditLogRepository;
import com.finset.key_fin.payment.repository.PrepareTransferRepository;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;

@Component
@RequiredArgsConstructor
public class TransferWriter {

	private final PrepareTransferRepository prepareTransferRepository;
	private final AccountRepository accountRepository;
	private final UserRepository userRepository;
	private final AuditLogRepository auditLogRepository;
	private final TransferPurposeResolver purposeResolver;
	private final ApplicationEventPublisher events;

	public record ApprovalContext(long transferId, long userId, String userKey, TransferStatus status, String institutionTxNo,
			long amount, Long fromAccountId, String fromAccountNo, String toAccountNo, String purposeName) {
	}

	@Transactional(readOnly = true)
	public ApprovalContext load(long userId, long transferId) {
		PrepareTransfer transfer = prepareTransferRepository.findByIdAndUserId(transferId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.TRANSFER_NOT_FOUND));
		if (!transfer.isProposed() && !transfer.isApproved()) {
			throw new BusinessException(PaymentErrorCode.TRANSFER_NOT_PROPOSED);
		}
		String userKey = userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND))
				.getFinUserKey();
		Map<Long, Account> accounts = accountRepository
				.findAllByIdInAndUserId(List.of(transfer.getFromAccountId(), transfer.getToAccountId()), userId)
				.stream().collect(Collectors.toMap(Account::getId, a -> a));
		Account from = accounts.get(transfer.getFromAccountId());
		Account to = accounts.get(transfer.getToAccountId());
		if (from == null || to == null) {
			throw new BusinessException(PaymentErrorCode.TRANSFER_ACCOUNT_INELIGIBLE);
		}
		return new ApprovalContext(transfer.getId(), userId, userKey, transfer.getStatus(), transfer.getInstitutionTxNo(),
				transfer.getRequiredAmount(), from.getId(), from.getFinAccountNo(), to.getFinAccountNo(),
				purposeResolver.nameOf(transfer));
	}

	@Transactional
	public void hold(long userId, long transferId, String basis) {
		auditLogRepository.save(AuditLog.transfer(userId, AuditAction.HOLD, transferId, basis));
	}

	/** 행 잠금 — 같은 제안을 동시에 승인하면 두 번째는 첫 커밋을 기다린 뒤 APPROVED를 보고 409. */
	@Transactional
	public void approve(long userId, long transferId, String institutionTxNo) {
		PrepareTransfer transfer = lockedTransfer(userId, transferId);
		if (!transfer.isProposed()) {
			throw new BusinessException(PaymentErrorCode.TRANSFER_NOT_PROPOSED);
		}
		transfer.approve(institutionTxNo);
	}

	@Transactional
	public TransferApproveResponse complete(long userId, long transferId, FinanceTransferResult result, LocalDateTime now,
			boolean notify) {
		PrepareTransfer transfer = lockedTransfer(userId, transferId);
		if (!transfer.isApproved()) {
			return response(transfer);
		}
		if (result.isSuccess()) {
			transfer.markExecuted(now);
			auditLogRepository.save(AuditLog.transfer(userId, AuditAction.EXECUTE, transferId,
					"금융망 " + result.responseCode() + " — 기관거래고유번호 " + transfer.getInstitutionTxNo()
							+ ", 금액 " + transfer.getRequiredAmount()
							+ ", 계좌 " + transfer.getFromAccountId() + "→" + transfer.getToAccountId()));
		} else {
			String reason = result.responseCode() + " " + (result.status() == FinanceTransferResult.Status.INSUFFICIENT_BALANCE
					? "출금 계좌 잔액 부족" : "은행 이체 한도 초과");
			transfer.markFailed(reason);
			auditLogRepository.save(AuditLog.transfer(userId, AuditAction.FAIL, transferId,
					reason + " — 기관거래고유번호 " + transfer.getInstitutionTxNo() + ", 금액 " + transfer.getRequiredAmount()));
		}
		if (notify) {
			events.publishEvent(new TransferCompleted(userId, transferId, transfer.getStatus()));
		}
		return response(transfer);
	}

	private PrepareTransfer lockedTransfer(long userId, long transferId) {
		return prepareTransferRepository.findByIdAndUserIdForUpdate(transferId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.TRANSFER_NOT_FOUND));
	}

	private static TransferApproveResponse response(PrepareTransfer transfer) {
		return new TransferApproveResponse(transfer.getId(), transfer.getStatus(), transfer.getExecutedAt(), transfer.getFailReason());
	}
}
