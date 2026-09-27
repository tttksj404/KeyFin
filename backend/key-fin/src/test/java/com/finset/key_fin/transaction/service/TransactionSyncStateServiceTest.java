package com.finset.key_fin.transaction.service;

import com.finset.key_fin.transaction.entity.TransactionAssetType;
import com.finset.key_fin.transaction.entity.TransactionSyncState;
import com.finset.key_fin.transaction.repository.TransactionSyncStateRepository;
import com.finset.key_fin.user.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class TransactionSyncStateServiceTest {

	private static final long USER_ID = 1L;
	private static final long ACCOUNT_ID = 3L;
	private static final LocalDate TODAY = LocalDate.of(2026, 9, 15);

	@Mock
	private TransactionSyncStateRepository syncStateRepository;

	private TransactionSyncStateService syncStateService;
	private User user;

	@BeforeEach
	void setUp() {
		syncStateService = new TransactionSyncStateService(syncStateRepository);
		user = User.create("qwer@qwer.com", "password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
	}

	@Test
	void 최초_동기화은_어제부터_오늘까지_조회한다() {
		given(syncStateRepository.findByUserIdAndAssetTypeAndAssetId(
				USER_ID, TransactionAssetType.ACCOUNT, ACCOUNT_ID))
				.willReturn(Optional.empty());

		LocalDate startDate = syncStateService.calculateSyncStartDate(
				USER_ID, TransactionAssetType.ACCOUNT, ACCOUNT_ID, TODAY);

		assertThat(startDate).isEqualTo(TODAY.minusDays(1));
	}

	@Test
	void 기존_동기화은_마지막_성공일의_하루_전부터_오늘까지_조회한다() {
		TransactionSyncState state = TransactionSyncState.create(
				user, TransactionAssetType.ACCOUNT, ACCOUNT_ID);
		state.recordSyncSuccess(LocalDateTime.of(2026, 9, 14, 10, 30));
		given(syncStateRepository.findByUserIdAndAssetTypeAndAssetId(
				USER_ID, TransactionAssetType.ACCOUNT, ACCOUNT_ID))
				.willReturn(Optional.of(state));

		LocalDate startDate = syncStateService.calculateSyncStartDate(
				USER_ID, TransactionAssetType.ACCOUNT, ACCOUNT_ID, TODAY);

		assertThat(startDate).isEqualTo(LocalDate.of(2026, 9, 13));
	}

	@Test
	void 상태가_없으면_성공_상태를_새로_저장한다() {
		LocalDateTime syncedAt = LocalDateTime.of(2026, 9, 15, 10, 30);
		given(syncStateRepository.findByUserIdAndAssetTypeAndAssetId(
				USER_ID, TransactionAssetType.ACCOUNT, ACCOUNT_ID))
				.willReturn(Optional.empty());

		syncStateService.recordSyncSuccess(
				user, TransactionAssetType.ACCOUNT, ACCOUNT_ID, syncedAt);

		ArgumentCaptor<TransactionSyncState> captor = ArgumentCaptor.forClass(TransactionSyncState.class);
		verify(syncStateRepository).save(captor.capture());
		assertThat(captor.getValue().getUser()).isSameAs(user);
		assertThat(captor.getValue().getAssetType()).isEqualTo(TransactionAssetType.ACCOUNT);
		assertThat(captor.getValue().getAssetId()).isEqualTo(ACCOUNT_ID);
		assertThat(captor.getValue().getLastSyncedAt()).isEqualTo(syncedAt);
	}

	@Test
	void 기존_상태가_있으면_마지막_성공_시각을_변경한다() {
		TransactionSyncState state = TransactionSyncState.create(
				user, TransactionAssetType.ACCOUNT, ACCOUNT_ID);
		LocalDateTime syncedAt = LocalDateTime.of(2026, 9, 15, 10, 30);
		given(syncStateRepository.findByUserIdAndAssetTypeAndAssetId(
				USER_ID, TransactionAssetType.ACCOUNT, ACCOUNT_ID))
				.willReturn(Optional.of(state));

		syncStateService.recordSyncSuccess(
				user, TransactionAssetType.ACCOUNT, ACCOUNT_ID, syncedAt);

		assertThat(state.getLastSyncedAt()).isEqualTo(syncedAt);
		verify(syncStateRepository).save(state);
	}
}

