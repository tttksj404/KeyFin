package com.finset.key_fin.payment.service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Map;
import org.springframework.data.domain.Limit;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.global.finance.client.FinanceHeaderFactory;
import com.finset.key_fin.payment.client.FinanceTransferClient;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult;
import com.finset.key_fin.payment.dto.response.TransferApproveResponse;
import com.finset.key_fin.payment.dto.response.TransferDetailResponse;
import com.finset.key_fin.payment.dto.response.TransferListResponse;
import com.finset.key_fin.payment.dto.response.TransferResponse;
import com.finset.key_fin.payment.entity.AuditLog;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.repository.AuditLogRepository;
import com.finset.key_fin.payment.repository.PrepareTransferRepository;
import com.finset.key_fin.payment.service.TransferWriter.ApprovalContext;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class TransferService {

	static final String SUMMARY_PREFIX = "KeyFin 결제 준비 - ";
	static final String POSTPONE_BASIS = "사용자 보류(나중에)";
	static final int DEFAULT_SIZE = 20;
	static final int MAX_SIZE = 100;
	private static final DateTimeFormatter MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");

	private final PrepareTransferRepository prepareTransferRepository;
	private final UserSettingsRepository userSettingsRepository;
	private final AccountRepository accountRepository;
	private final AuditLogRepository auditLogRepository;
	private final TransferPurposeResolver purposeResolver;
	private final TransferWriter writer;
	private final FinanceTransferClient financeTransferClient;
	private final FinanceHeaderFactory headerFactory;
	private final Clock clock;

	/** month는 대상 출금일(due_date) 기준 yyyyMM. cursor는 직전 페이지 마지막 id — 최신순이라 그보다 작은 id를 읽는다. */
	@Transactional(readOnly = true)
	public TransferListResponse list(long userId, TransferStatus status, String month, Long cursor, Integer size) {
		YearMonth target = parseMonth(month);
		int pageSize = resolveSize(size);
		if (cursor != null && cursor <= 0) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		List<PrepareTransfer> rows = prepareTransferRepository.findPage(
				userId, status,
				target == null ? null : target.atDay(1),
				target == null ? null : target.plusMonths(1).atDay(1),
				cursor, Limit.of(pageSize + 1));
		boolean hasNext = rows.size() > pageSize;
		List<PrepareTransfer> page = hasNext ? rows.subList(0, pageSize) : rows;
		Map<Long, String> names = purposeResolver.namesOf(page);
		return new TransferListResponse(
				page.stream().map(t -> TransferResponse.of(t, names.get(t.getId()))).toList(),
				hasNext ? page.getLast().getId() : null);
	}

	@Transactional(readOnly = true)
	public TransferDetailResponse detail(long userId, long transferId) {
		PrepareTransfer transfer = prepareTransferRepository.findByIdAndUserId(transferId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.TRANSFER_NOT_FOUND));
		return TransferDetailResponse.of(
				TransferResponse.of(transfer, purposeResolver.nameOf(transfer)),
				auditLogRepository.findAllByTargetTypeAndTargetIdOrderByIdAsc(
						AuditLog.TARGET_PREPARE_TRANSFER, String.valueOf(transferId)));
	}

	private static YearMonth parseMonth(String month) {
		if (month == null || month.isBlank()) {
			return null;
		}
		try {
			return YearMonth.parse(month, MONTH_FORMAT);
		} catch (DateTimeParseException e) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
	}

	private static int resolveSize(Integer size) {
		int resolved = size == null ? DEFAULT_SIZE : size;
		if (resolved < 1 || resolved > MAX_SIZE) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		return resolved;
	}

	/** 트랜잭션 없음 — APPROVED 커밋 후 금융망 이체, 응답 유실 시 같은 기관거래고유번호로 재시도하기 위해. */
	public TransferApproveResponse approve(long userId, long transferId) {
		ApprovalContext ctx = writer.load(userId, transferId);
		String institutionTxNo = ctx.institutionTxNo();
		if (ctx.status() == TransferStatus.PROPOSED) {
			checkSafeguards(ctx);
			institutionTxNo = headerFactory.newTransactionUniqueNo();
			writer.approve(userId, transferId, institutionTxNo);
			log.info("이체 승인: transferId={}, userId={}, institutionTxNo={}, amount={}",
					transferId, userId, institutionTxNo, ctx.amount());
		}
		FinanceTransferResult result = transfer(ctx, institutionTxNo);
		TransferApproveResponse response = writer.complete(userId, transferId, result, LocalDateTime.now(clock), true);
		if (!result.isSuccess()) {
			throw new BusinessException(result.status() == FinanceTransferResult.Status.INSUFFICIENT_BALANCE
					? PaymentErrorCode.TRANSFER_INSUFFICIENT_BALANCE
					: PaymentErrorCode.TRANSFER_BANK_LIMIT);
		}
		return response;
	}

	/** APPROVED로 남은 건(응답 유실)을 저장된 번호로 재전송한다. 이번에도 결과를 못 받으면 다음 회차에 다시 본다. */
	public void recoverApproved() {
		List<PrepareTransfer> stuck = prepareTransferRepository.findAllByStatus(TransferStatus.APPROVED);
		int failed = 0;
		for (PrepareTransfer transfer : stuck) {
			try {
				ApprovalContext ctx = writer.load(transfer.getUserId(), transfer.getId());
				FinanceTransferResult result = transfer(ctx, ctx.institutionTxNo());
				writer.complete(ctx.userId(), ctx.transferId(), result, LocalDateTime.now(clock), false);
			} catch (RuntimeException e) {
				failed++;
				log.warn("이체 복구 실패 — 다음 회차에 재시도: transferId={}, cause={}", transfer.getId(), e.toString());
			}
		}
		log.info("이체 복구 완료: candidates={}, failed={}", stuck.size(), failed);
	}

	private FinanceTransferResult transfer(ApprovalContext ctx, String institutionTxNo) {
		return financeTransferClient.transfer(
				ctx.userKey(), institutionTxNo, ctx.fromAccountNo(), ctx.toAccountNo(), ctx.amount(),
				SUMMARY_PREFIX + ctx.purposeName());
	}

	@Transactional
	public void postpone(long userId, long transferId) {
		PrepareTransfer transfer = prepareTransferRepository.findByIdAndUserId(transferId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.TRANSFER_NOT_FOUND));
		if (!transfer.isProposed()) {
			throw new BusinessException(PaymentErrorCode.TRANSFER_NOT_PROPOSED);
		}
		auditLogRepository.save(AuditLog.transfer(userId, AuditAction.HOLD, transferId,
				POSTPONE_BASIS + " — 출금일 " + transfer.getDueDate() + ", 제안액 " + transfer.getRequiredAmount()));
	}

	private void checkSafeguards(ApprovalContext ctx) {
		UserSettings settings = userSettingsRepository.findById(ctx.userId())
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_SETTINGS_NOT_FOUND));
		if (!settings.isTransferConsent()) {
			hold(ctx, PaymentErrorCode.TRANSFER_CONSENT_OFF, "transfer_consent=false");
		}
		if (settings.getTransferLimitOnce() != null && ctx.amount() > settings.getTransferLimitOnce()) {
			hold(ctx, PaymentErrorCode.TRANSFER_LIMIT_ONCE,
					"금액 " + ctx.amount() + " > 1회 한도 " + settings.getTransferLimitOnce());
		}
		if (settings.getTransferLimitDaily() != null) {
			LocalDate today = LocalDate.now(clock);
			long executedToday = prepareTransferRepository.sumExecutedAmount(
					ctx.userId(), today.atStartOfDay(), today.plusDays(1).atStartOfDay());
			if (executedToday + ctx.amount() > settings.getTransferLimitDaily()) {
				hold(ctx, PaymentErrorCode.TRANSFER_LIMIT_DAILY,
						"오늘 실행 " + executedToday + " + 금액 " + ctx.amount() + " > 1일 한도 " + settings.getTransferLimitDaily());
			}
		}
		Account from = accountRepository.findByIdAndUserId(ctx.fromAccountId(), ctx.userId()).orElse(null);
		if (from == null || !from.isIncome() || !from.isManaged()) {
			hold(ctx, PaymentErrorCode.TRANSFER_ACCOUNT_INELIGIBLE,
					"출금 계좌 " + ctx.fromAccountId() + " 수입·관리 대상 아님");
		}
	}

	private void hold(ApprovalContext ctx, PaymentErrorCode code, String detail) {
		writer.hold(ctx.userId(), ctx.transferId(), code.getCode() + " " + code.getMessage() + " — " + detail);
		throw new BusinessException(code);
	}
}
