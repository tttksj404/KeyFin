package com.finset.key_fin.link.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.dto.response.FinanceAccount;
import com.finset.key_fin.link.dto.response.FinanceCard;
import com.finset.key_fin.link.service.AssetSyncService.SyncedAssets;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class AssetSyncServiceTest {

	private static final long USER_ID = 1L;
	private static final FinanceAccount KB_ACCOUNT =
			new FinanceAccount("004", "국민은행", "0041456503815897", "국민 수시입출금", "1", 3_000_000L, "KRW");
	private static final FinanceAccount SHINHAN_ACCOUNT =
			new FinanceAccount("088", "신한은행", "0880680068408149", "신한 수시입출금", "1", 125_000L, "KRW");
	private static final FinanceAccount DEPOSIT_ACCOUNT =
			new FinanceAccount("020", "우리은행", "0204667768182760", "우리 정기예금", "2", 8_003_477L, "KRW");
	private static final FinanceCard SHINHAN_CARD = new FinanceCard(
			"1005872701650761", "725", "1005-x", "1005", "신한카드", "신한 딥디저트 카드",
			"20310910", "0880680068408149", "1"
	);

	@Mock
	private UserRepository userRepository;

	@Mock
	private AccountRepository accountRepository;

	@Mock
	private CardRepository cardRepository;

	@InjectMocks
	private AssetSyncService syncService;

	private User user;

	@BeforeEach
	void setUp() {
		user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
		user.connectFinance("finance-user-key");
		lenient().when(accountRepository.saveAll(anyList())).thenAnswer(invocation -> invocation.getArgument(0));
		lenient().when(cardRepository.saveAll(anyList())).thenAnswer(invocation -> invocation.getArgument(0));
	}

	@Test
	void 수시입출금_계좌와_카드를_미선택_상태로_한_번에_저장하고_카드_출금계좌를_매칭한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findAllByUserId(USER_ID)).willReturn(List.of());
		given(cardRepository.findAllByUserId(USER_ID)).willReturn(List.of());

		SyncedAssets synced = syncService.sync(
				USER_ID, List.of(KB_ACCOUNT, SHINHAN_ACCOUNT, DEPOSIT_ACCOUNT), List.of(SHINHAN_CARD));

		ArgumentCaptor<List<Account>> accountCaptor = ArgumentCaptor.forClass(List.class);
		verify(accountRepository).saveAll(accountCaptor.capture());
		assertThat(accountCaptor.getValue())
				.extracting(Account::getFinAccountNo)
				.containsExactly("0041456503815897", "0880680068408149");
		assertThat(accountCaptor.getValue())
				.extracting(Account::getBankName, Account::getBalance)
				.containsExactly(
						org.assertj.core.groups.Tuple.tuple("국민은행", 3_000_000L),
						org.assertj.core.groups.Tuple.tuple("신한은행", 125_000L)
				);
		assertThat(accountCaptor.getValue()).allMatch(account -> account.getBalanceUpdatedAt() != null);
		assertThat(accountCaptor.getValue()).allMatch(account -> !account.isManaged());

		ArgumentCaptor<List<Card>> cardCaptor = ArgumentCaptor.forClass(List.class);
		verify(cardRepository).saveAll(cardCaptor.capture());
		Card card = cardCaptor.getValue().get(0);
		assertThat(card.getFinCardNo()).isEqualTo("1005872701650761");
		assertThat(card.getCvc()).isEqualTo("725");
		assertThat(card.getIssuerCode()).isEqualTo("1005");
		assertThat(card.isManaged()).isFalse();
		assertThat(card.getWithdrawalWeekday()).isEqualTo(1);
		assertThat(card.getWithdrawalAccount()).isNotNull();
		assertThat(card.getWithdrawalAccount().getFinAccountNo()).isEqualTo("0880680068408149");

		assertThat(synced.accountsByNo()).containsOnlyKeys("0041456503815897", "0880680068408149");
		assertThat(synced.cardsByNo()).containsOnlyKeys("1005872701650761");
	}

	@Test
	void 이미_저장된_자산은_새로_저장하지_않고_계좌_잔액_스냅샷을_갱신한다() {
		Account existingAccount = Account.sync(
				user, "0880680068408149", "088", "신한은행", 100_000L, LocalDateTime.now());
		existingAccount.link();
		Card existingCard = Card.sync(user, "1005872701650761", "000", "1005", "옛 카드명", null);
		existingCard.link();
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findAllByUserId(USER_ID)).willReturn(List.of(existingAccount));
		given(cardRepository.findAllByUserId(USER_ID)).willReturn(List.of(existingCard));

		SyncedAssets synced = syncService.sync(USER_ID, List.of(SHINHAN_ACCOUNT), List.of(SHINHAN_CARD));

		verify(accountRepository).saveAll(List.of());
		verify(cardRepository).saveAll(List.of());
		assertThat(synced.accountsByNo().get("0880680068408149")).isSameAs(existingAccount);
		assertThat(synced.cardsByNo().get("1005872701650761")).isSameAs(existingCard);
		assertThat(existingAccount.getBalance()).isEqualTo(125_000L);
		assertThat(existingAccount.getBankName()).isEqualTo("신한은행");
		assertThat(existingAccount.isManaged()).isTrue();
		assertThat(existingCard.isManaged()).isTrue();
	}

	@Test
	void 출금계좌가_동기화_대상에_없는_카드는_출금계좌_없이_저장한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findAllByUserId(USER_ID)).willReturn(List.of());
		given(cardRepository.findAllByUserId(USER_ID)).willReturn(List.of());

		SyncedAssets synced = syncService.sync(USER_ID, List.of(), List.of(SHINHAN_CARD));

		ArgumentCaptor<List<Card>> cardCaptor = ArgumentCaptor.forClass(List.class);
		verify(cardRepository).saveAll(cardCaptor.capture());
		assertThat(cardCaptor.getValue().get(0).getWithdrawalAccount()).isNull();
		assertThat(synced.cardsByNo()).containsKey("1005872701650761");
	}

	@Test
	void 탈퇴했거나_없는_사용자는_동기화할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> syncService.sync(USER_ID, List.of(KB_ACCOUNT), List.of()))
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(UserErrorCode.USER_NOT_FOUND);
	}
}
