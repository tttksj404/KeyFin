package com.finset.key_fin.transaction.service;

import com.finset.key_fin.transaction.repository.SubcategoryQueryRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.transaction.dto.request.TransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.request.TransactionMemoUpdateRequest;
import com.finset.key_fin.transaction.dto.request.BulkTransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.request.BulkTransactionClassificationRequest.Item;
import com.finset.key_fin.transaction.dto.response.TransactionListResponse;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import com.finset.key_fin.transaction.exception.TransactionErrorCode;
import com.finset.key_fin.transaction.repository.TransactionQueryRepository;
import com.finset.key_fin.transaction.repository.TransactionQueryRow;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.transaction.repository.TransactionSearchCondition;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.springframework.context.ApplicationEventPublisher;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.never;

@ExtendWith(MockitoExtension.class)
class TransactionServiceTest {

	private static final long USER_ID = 1L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private TransactionRepository transactionRepository;

	@Mock
	private TransactionQueryRepository transactionQueryRepository;

	private TransactionService transactionService;
	@Mock private RoomStickerService roomStickerService;

	@BeforeEach
	void setUp() {
		Clock clock = Clock.fixed(Instant.parse("2026-09-14T00:00:00Z"), ZoneOffset.UTC);
		transactionService = new TransactionService(mock(ApplicationEventPublisher.class),
				mock(SubcategoryQueryRepository.class), userRepository, transactionRepository,
				transactionQueryRepository, clock, roomStickerService);
	}

	@Test
	void 필터와_월을_적용해_거래를_조회한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		given(transactionQueryRepository.findTransactions(org.mockito.ArgumentMatchers.any()))
				.willReturn(List.of(row(501L)));

		TransactionListResponse response = transactionService.getTransactions(
				USER_ID, "202609", 1, 102, 3L, 7L, null, 20);

		assertThat(response.items()).hasSize(1);
		assertThat(response.items().getFirst().id()).isEqualTo(501L);
		assertThat(response.nextCursor()).isNull();
		ArgumentCaptor<TransactionSearchCondition> captor = ArgumentCaptor.forClass(TransactionSearchCondition.class);
		verify(transactionQueryRepository).findTransactions(captor.capture());
		assertThat(captor.getValue())
				.extracting("startDate", "endDate", "envelopeId", "subcategoryId", "accountId", "cardId", "limit")
				.containsExactly(LocalDate.of(2026, 9, 1), LocalDate.of(2026, 10, 1), 1, 102, 3L, 7L, 21);
	}

	@Test
	void 월을_생략하면_KST_현재_월을_사용한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		given(transactionQueryRepository.findTransactions(org.mockito.ArgumentMatchers.any())).willReturn(List.of());

		transactionService.getTransactions(USER_ID, null, null, null, null, null, null, null);

		ArgumentCaptor<TransactionSearchCondition> captor = ArgumentCaptor.forClass(TransactionSearchCondition.class);
		verify(transactionQueryRepository).findTransactions(captor.capture());
		assertThat(captor.getValue().startDate()).isEqualTo(LocalDate.of(2026, 9, 1));
		assertThat(captor.getValue().limit()).isEqualTo(21);
	}

	@Test
	void 다음_거래가_있으면_마지막_반환_ID를_cursor로_제공한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		given(transactionQueryRepository.findTransactions(org.mockito.ArgumentMatchers.any()))
				.willReturn(List.of(row(10L), row(9L), row(8L)));

		TransactionListResponse response = transactionService.getTransactions(
				USER_ID, "202609", null, null, null, null, null, 2);

		assertThat(response.items()).extracting("id").containsExactly(10L, 9L);
		assertThat(response.nextCursor()).isEqualTo(9L);
	}

	@Test
	void 미확정_거래를_전체_기간에서_조회한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		given(transactionQueryRepository.findPendingTransactions(USER_ID, null, 3))
				.willReturn(List.of(row(10L), row(9L), row(8L)));

		TransactionListResponse response = transactionService.getPendingTransactions(USER_ID, null, 2);

		assertThat(response.items()).extracting("id").containsExactly(10L, 9L);
		assertThat(response.nextCursor()).isEqualTo(9L);
		verify(transactionQueryRepository).findPendingTransactions(USER_ID, null, 3);
	}

	@Test
	void 거래를_세분류로_확정한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		Transaction transaction = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		given(userRepository.findActiveByIdForUpdate(USER_ID)).willReturn(Optional.of(user));
		given(transactionRepository.findByIdAndUserId(501L, USER_ID)).willReturn(Optional.of(transaction));
		given(transactionQueryRepository.existsSubcategory(102)).willReturn(true);

		var response = transactionService.classifyTransaction(
				USER_ID, 501L, new TransactionClassificationRequest(102, null, null)
		);

		assertThat(response.subcategoryId()).isEqualTo(102);
		assertThat(response.confirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
		assertThat(response.excludeTag()).isEqualTo(ExcludeTag.NONE);
	}

	@Test
	void 거래를_예산_제외로_확정한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		Transaction transaction = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		given(userRepository.findActiveByIdForUpdate(USER_ID)).willReturn(Optional.of(user));
		given(transactionRepository.findByIdAndUserId(501L, USER_ID)).willReturn(Optional.of(transaction));

		var response = transactionService.classifyTransaction(
				USER_ID, 501L, new TransactionClassificationRequest(null, ExcludeTag.BUDGET_EXCLUDED, null)
		);

		assertThat(response.excludeTag()).isEqualTo(ExcludeTag.BUDGET_EXCLUDED);
		assertThat(response.subcategoryId()).isNull();
		assertThat(response.adjustedAmount()).isNull();
		assertThat(response.confirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 세분류와_제외_태그를_동시에_입력하면_거절한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		Transaction transaction = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		given(userRepository.findActiveByIdForUpdate(USER_ID)).willReturn(Optional.of(user));
		given(transactionRepository.findByIdAndUserId(501L, USER_ID)).willReturn(Optional.of(transaction));

		assertThatThrownBy(() -> transactionService.classifyTransaction(
				USER_ID, 501L, new TransactionClassificationRequest(102, ExcludeTag.DUTCH, 20_000L)
		)).isInstanceOfSatisfying(BusinessException.class,
				exception -> assertThat(exception.getErrorCode())
						.isEqualTo(TransactionErrorCode.INVALID_CLASSIFICATION));
	}

	@Test
	void 다른_사용자의_거래는_찾을_수_없다() {
		given(userRepository.findActiveByIdForUpdate(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		given(transactionRepository.findByIdAndUserId(999L, USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> transactionService.classifyTransaction(
				USER_ID, 999L, new TransactionClassificationRequest(102, null, null)
		)).isInstanceOfSatisfying(BusinessException.class,
				exception -> assertThat(exception.getErrorCode())
						.isEqualTo(TransactionErrorCode.TRANSACTION_NOT_FOUND));
	}

	@Test
	void 환급_입금을_세분류와_RESTORE로_확정한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		Transaction transaction = transaction(502L, TransactionType.DEPOSIT, TransactionStatus.NORMAL, 20_000L);
		given(userRepository.findActiveByIdForUpdate(USER_ID)).willReturn(Optional.of(user));
		given(transactionRepository.findByIdAndUserId(502L, USER_ID)).willReturn(Optional.of(transaction));
		given(transactionQueryRepository.existsSubcategory(301)).willReturn(true);

		var response = transactionService.classifyTransaction(
				USER_ID, 502L, new TransactionClassificationRequest(301, ExcludeTag.RESTORE, null)
		);

		assertThat(response.subcategoryId()).isEqualTo(301);
		assertThat(response.excludeTag()).isEqualTo(ExcludeTag.RESTORE);
		assertThat(response.confirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 거래_메모를_수정한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		Transaction transaction = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(transactionRepository.findByIdAndUserId(501L, USER_ID)).willReturn(Optional.of(transaction));

		transactionService.updateTransactionMemo(
				USER_ID, 501L, new TransactionMemoUpdateRequest("  회식 메모  "));

		assertThat(transaction.getMemo()).isEqualTo("회식 메모");
	}

	@Test
	void 다른_사용자의_거래_메모는_수정할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		given(transactionRepository.findByIdAndUserId(999L, USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> transactionService.updateTransactionMemo(
				USER_ID, 999L, new TransactionMemoUpdateRequest("메모")))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.TRANSACTION_NOT_FOUND));
	}

	@Test
	void 미확정_거래를_일괄_분류한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		Transaction first = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		Transaction second = transaction(502L, TransactionType.WITHDRAW, TransactionStatus.NORMAL, 30_000L);
		given(userRepository.findActiveByIdForUpdate(USER_ID)).willReturn(Optional.of(user));
		given(transactionRepository.findAllByIdInAndUserId(java.util.Set.of(501L, 502L), USER_ID))
				.willReturn(List.of(first, second));
		given(transactionQueryRepository.existsSubcategory(102)).willReturn(true);
		given(transactionRepository.countByUserIdAndConfirmStatusAndStatusAndTransactionTypeNot(
				USER_ID, ConfirmStatus.PENDING, TransactionStatus.NORMAL, TransactionType.DEPOSIT))
				.willReturn(0L);
		var request = new BulkTransactionClassificationRequest(List.of(
				new Item(501L, 102, null, null),
				new Item(502L, null, ExcludeTag.DUTCH, 15_000L)
		));

		var response = transactionService.classifyPendingTransactions(USER_ID, request);

		assertThat(response.confirmed()).isEqualTo(2);
		assertThat(response.pendingRemain()).isZero();
		assertThat(first.getSubcategoryId()).isEqualTo(102);
		assertThat(second.getExcludeTag()).isEqualTo(ExcludeTag.DUTCH);
		assertThat(second.getAdjustedAmount()).isEqualTo(15_000L);
	}

	@Test
	void 미확정_거래를_예산_제외로_일괄_분류한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		Transaction transaction = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		given(userRepository.findActiveByIdForUpdate(USER_ID)).willReturn(Optional.of(user));
		given(transactionRepository.findAllByIdInAndUserId(java.util.Set.of(501L), USER_ID))
				.willReturn(List.of(transaction));
		given(transactionRepository.countByUserIdAndConfirmStatusAndStatusAndTransactionTypeNot(
				USER_ID, ConfirmStatus.PENDING, TransactionStatus.NORMAL, TransactionType.DEPOSIT))
				.willReturn(0L);
		var request = new BulkTransactionClassificationRequest(List.of(
				new Item(501L, null, ExcludeTag.BUDGET_EXCLUDED, null)
		));

		var response = transactionService.classifyPendingTransactions(USER_ID, request);

		assertThat(response.confirmed()).isEqualTo(1);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.BUDGET_EXCLUDED);
		assertThat(transaction.getSubcategoryId()).isNull();
		assertThat(transaction.getAdjustedAmount()).isNull();
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 일괄_분류에_중복_거래_ID가_있으면_거절한다() {
		given(userRepository.findActiveByIdForUpdate(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		var request = new BulkTransactionClassificationRequest(List.of(
				new Item(501L, 102, null, null),
				new Item(501L, null, ExcludeTag.SELF_TRANSFER, null)
		));

		assertThatThrownBy(() -> transactionService.classifyPendingTransactions(USER_ID, request))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.INVALID_CLASSIFICATION));
		verify(transactionRepository, never()).findAllByIdInAndUserId(
				org.mockito.ArgumentMatchers.anyCollection(), org.mockito.ArgumentMatchers.anyLong());
	}

	@Test
	void 일괄_분류에_다른_사용자의_거래가_포함되면_거절한다() {
		given(userRepository.findActiveByIdForUpdate(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		Transaction first = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		given(transactionRepository.findAllByIdInAndUserId(java.util.Set.of(501L, 999L), USER_ID))
				.willReturn(List.of(first));
		var request = new BulkTransactionClassificationRequest(List.of(
				new Item(501L, 102, null, null),
				new Item(999L, 102, null, null)
		));

		assertThatThrownBy(() -> transactionService.classifyPendingTransactions(USER_ID, request))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.TRANSACTION_NOT_FOUND));
	}

	@Test
	void 이미_확정된_거래가_일괄_분류에_포함되면_거절한다() {
		given(userRepository.findActiveByIdForUpdate(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		Transaction transaction = transaction(501L, TransactionType.CARD, TransactionStatus.NORMAL, 40_000L);
		ReflectionTestUtils.setField(transaction, "confirmStatus", ConfirmStatus.CONFIRMED);
		given(transactionRepository.findAllByIdInAndUserId(java.util.Set.of(501L), USER_ID))
				.willReturn(List.of(transaction));
		var request = new BulkTransactionClassificationRequest(
				List.of(new Item(501L, 102, null, null)));

		assertThatThrownBy(() -> transactionService.classifyPendingTransactions(USER_ID, request))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.CLASSIFICATION_NOT_ALLOWED));
	}

	@Test
	void 잘못된_월은_거절한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));

		assertThatThrownBy(() -> transactionService.getTransactions(
				USER_ID, "2026-09", null, null, null, null, null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(TransactionErrorCode.INVALID_MONTH));
	}

	@Test
	void 페이지_크기_범위를_검증한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));

		assertThatThrownBy(() -> transactionService.getTransactions(
				USER_ID, "202609", null, null, null, null, null, 101))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(TransactionErrorCode.INVALID_PAGE_SIZE));
	}

	@Test
	void 활성_사용자가_없으면_거래를_조회할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> transactionService.getTransactions(
				USER_ID, "202609", null, null, null, null, null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(transactionQueryRepository);
	}

	private TransactionQueryRow row(long id) {
		return new TransactionQueryRow(
				id, TransactionType.CARD, "메가커피", 4_500L,
				LocalDate.of(2026, 9, 8), LocalTime.of(14, 21),
				1, 102, "카페", ConfirmStatus.AUTO, ExcludeTag.NONE,
				TransactionStatus.NORMAL, null, null, 7L, null
		);
	}

	private Transaction transaction(long id, TransactionType type, TransactionStatus status, long amount) {
		try {
			var constructor = Transaction.class.getDeclaredConstructor();
			constructor.setAccessible(true);
			Transaction transaction = constructor.newInstance();
			ReflectionTestUtils.setField(transaction, "id", id);
			ReflectionTestUtils.setField(transaction, "transactionType", type);
			ReflectionTestUtils.setField(transaction, "status", status);
			ReflectionTestUtils.setField(transaction, "amount", amount);
			return transaction;
		} catch (ReflectiveOperationException exception) {
			throw new IllegalStateException(exception);
		}
	}
}
