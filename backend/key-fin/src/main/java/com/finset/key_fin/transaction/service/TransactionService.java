package com.finset.key_fin.transaction.service;

import com.finset.key_fin.budget.event.EnvelopeSpendingChanged;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.transaction.dto.request.TransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.request.TransactionMemoUpdateRequest;
import com.finset.key_fin.transaction.dto.request.BulkTransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.response.BulkTransactionClassificationResponse;
import com.finset.key_fin.transaction.dto.response.TransactionClassificationResponse;
import com.finset.key_fin.transaction.dto.response.TransactionListResponse;
import com.finset.key_fin.transaction.dto.response.TransactionListResponse.TransactionItem;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import com.finset.key_fin.transaction.exception.TransactionErrorCode;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRepository;
import com.finset.key_fin.transaction.repository.TransactionQueryRepository;
import com.finset.key_fin.transaction.repository.TransactionQueryRow;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.transaction.repository.TransactionSearchCondition;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Stream;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class TransactionService {

	private static final int DEFAULT_SIZE = 20;
	private static final int MAX_SIZE = 100;
	private static final DateTimeFormatter MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");

	private final ApplicationEventPublisher events;
	private final SubcategoryQueryRepository subcategoryQueryRepository;
	private final UserRepository userRepository;
	private final TransactionRepository transactionRepository;
	private final TransactionQueryRepository transactionQueryRepository;
	private final Clock clock;
	private final RoomStickerService roomStickerService;

	@Transactional(readOnly = true)
	public TransactionListResponse getTransactions(
			long userId,
			String month,
			Integer envelopeId,
			Integer subcategoryId,
			Long accountId,
			Long cardId,
			Long cursor,
			Integer size
	) {
		validateActiveUser(userId);
		YearMonth targetMonth = parseMonth(month);
		int pageSize = validateSize(size);
		validatePositiveFilter(envelopeId);
		validatePositiveFilter(subcategoryId);
		validatePositiveFilter(accountId);
		validatePositiveFilter(cardId);
		validatePositiveFilter(cursor);

		List<TransactionQueryRow> rows = transactionQueryRepository.findTransactions(
				new TransactionSearchCondition(
						userId,
						targetMonth.atDay(1),
						targetMonth.plusMonths(1).atDay(1),
						envelopeId,
						subcategoryId,
						accountId,
						cardId,
						cursor,
						pageSize + 1
				)
		);

		boolean hasNext = rows.size() > pageSize;
		List<TransactionQueryRow> page = hasNext ? rows.subList(0, pageSize) : rows;
		Long nextCursor = hasNext ? page.getLast().id() : null;
		return new TransactionListResponse(page.stream().map(TransactionItem::from).toList(), nextCursor);
	}

	@Transactional(readOnly = true)
	public TransactionListResponse getPendingTransactions(long userId, Long cursor, Integer size) {
		validateActiveUser(userId);
		int pageSize = validateSize(size);
		validatePositiveFilter(cursor);

		List<TransactionQueryRow> rows = transactionQueryRepository.findPendingTransactions(
				userId, cursor, pageSize + 1
		);

		return toListResponse(rows, pageSize);
	}

	@Transactional
	public TransactionClassificationResponse classifyTransaction(
			long userId,
			long transactionId,
			TransactionClassificationRequest request
	) {
		lockActiveUser(userId);
		if (request == null) {
			throw new BusinessException(TransactionErrorCode.INVALID_CLASSIFICATION);
		}

		var transaction = transactionRepository.findByIdAndUserId(transactionId, userId)
				.orElseThrow(() -> new BusinessException(TransactionErrorCode.TRANSACTION_NOT_FOUND));
		applyClassification(userId, transaction, request);
		roomStickerService.synchronize(userId);
		return TransactionClassificationResponse.from(transaction);
	}

	@Transactional
	public BulkTransactionClassificationResponse classifyPendingTransactions(
			long userId,
			BulkTransactionClassificationRequest request
	) {
		lockActiveUser(userId);
		List<BulkTransactionClassificationRequest.Item> items = request.items();
		Set<Long> transactionIds = items.stream()
				.map(BulkTransactionClassificationRequest.Item::transactionId)
				.collect(Collectors.toSet());
		if (transactionIds.size() != items.size()) {
			throw new BusinessException(TransactionErrorCode.INVALID_CLASSIFICATION);
		}

		Map<Long, Transaction> transactionsById = transactionRepository
				.findAllByIdInAndUserId(transactionIds, userId)
				.stream()
				.collect(Collectors.toMap(Transaction::getId, Function.identity()));
		if (transactionsById.size() != transactionIds.size()) {
			throw new BusinessException(TransactionErrorCode.TRANSACTION_NOT_FOUND);
		}

		for (BulkTransactionClassificationRequest.Item item : items) {
			Transaction transaction = transactionsById.get(item.transactionId());
			transaction.validatePendingClassificationTarget();
			applyClassification(userId, transaction, item.toClassificationRequest());
		}

		roomStickerService.synchronize(userId);
		long pendingRemain = transactionRepository
				.countByUserIdAndConfirmStatusAndStatusAndTransactionTypeNot(
						userId, ConfirmStatus.PENDING, TransactionStatus.NORMAL, TransactionType.DEPOSIT
				);
		return new BulkTransactionClassificationResponse(items.size(), pendingRemain);
	}

	private void applyClassification(long userId, Transaction transaction,
			TransactionClassificationRequest request) {
		Integer before = transaction.getSubcategoryId();
		applyClassificationInternal(transaction, request);
		publishEnvelopeChanged(userId, before, transaction.getSubcategoryId());
	}

	private void publishEnvelopeChanged(long userId, Integer before, Integer after) {
		Stream.of(before, after)
				.filter(Objects::nonNull)
				.distinct()
				.map(subcategoryQueryRepository::findEnvelopeId)
				.flatMap(Optional::stream)
				.distinct()
				.forEach(envelopeId -> events.publishEvent(new EnvelopeSpendingChanged(userId, envelopeId)));
	}

	private void applyClassificationInternal(Transaction transaction, TransactionClassificationRequest request) {
		boolean hasSubcategory = request.subcategoryId() != null;
		boolean hasExcludeTag = request.excludeTag() != null;
		boolean isRestore = request.excludeTag() == ExcludeTag.RESTORE;

		if (isRestore) {
			if (!hasSubcategory || request.adjustedAmount() != null) {
				throw new BusinessException(TransactionErrorCode.INVALID_CLASSIFICATION);
			}
			validateSubcategory(request.subcategoryId());
			transaction.confirmRestore(request.subcategoryId());
			return;
		}

		if (hasSubcategory == hasExcludeTag) {
			throw new BusinessException(TransactionErrorCode.INVALID_CLASSIFICATION);
		}

		if (hasSubcategory) {
			if (request.adjustedAmount() != null) {
				throw new BusinessException(TransactionErrorCode.INVALID_CLASSIFICATION);
			}
			validateSubcategory(request.subcategoryId());
			transaction.confirmSubcategory(request.subcategoryId());
		} else {
			transaction.confirmExclusion(request.excludeTag(), request.adjustedAmount());
		}

	}

	@Transactional
	public void updateTransactionMemo(
			long userId,
			long transactionId,
			TransactionMemoUpdateRequest request
	) {
		validateActiveUser(userId);
		var transaction = transactionRepository.findByIdAndUserId(transactionId, userId)
				.orElseThrow(() -> new BusinessException(TransactionErrorCode.TRANSACTION_NOT_FOUND));
		transaction.updateMemo(request.memo());
	}

	private void validateSubcategory(int subcategoryId) {
		if (subcategoryId <= 0 || !transactionQueryRepository.existsSubcategory(subcategoryId)) {
			throw new BusinessException(TransactionErrorCode.SUBCATEGORY_NOT_FOUND);
		}
	}

	private TransactionListResponse toListResponse(List<TransactionQueryRow> rows, int pageSize) {
		boolean hasNext = rows.size() > pageSize;
		List<TransactionQueryRow> page = hasNext ? rows.subList(0, pageSize) : rows;
		Long nextCursor = hasNext ? page.getLast().id() : null;
		return new TransactionListResponse(page.stream().map(TransactionItem::from).toList(), nextCursor);
	}

	private YearMonth parseMonth(String month) {
		if (month == null || month.isBlank()) {
			return YearMonth.now(clock.withZone(KST));
		}
		try {
			return YearMonth.parse(month, MONTH_FORMAT);
		} catch (DateTimeParseException exception) {
			throw new BusinessException(TransactionErrorCode.INVALID_MONTH, exception);
		}
	}

	private int validateSize(Integer size) {
		int resolved = size == null ? DEFAULT_SIZE : size;
		if (resolved < 1 || resolved > MAX_SIZE) {
			throw new BusinessException(TransactionErrorCode.INVALID_PAGE_SIZE);
		}
		return resolved;
	}

	private void validatePositiveFilter(Number value) {
		if (value != null && value.longValue() <= 0) {
			throw new BusinessException(TransactionErrorCode.INVALID_SEARCH_FILTER);
		}
	}

	private void validateActiveUser(long userId) {
		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}

	private void lockActiveUser(long userId) {
		userRepository.findActiveByIdForUpdate(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}
}
