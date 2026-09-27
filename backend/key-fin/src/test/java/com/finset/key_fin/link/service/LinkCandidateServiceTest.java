package com.finset.key_fin.link.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.ErrorCode;
import com.finset.key_fin.link.client.FinanceAccountClient;
import com.finset.key_fin.link.client.FinanceCardClient;
import com.finset.key_fin.link.dto.response.FinanceAccount;
import com.finset.key_fin.link.dto.response.FinanceCard;
import com.finset.key_fin.link.dto.response.LinkCandidatesResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.link.service.AssetSyncService.SyncedAssets;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.assertj.core.groups.Tuple;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class LinkCandidateServiceTest {

	private static final long USER_ID = 1L;
	private static final String FIN_USER_KEY = "finance-user-key";
	private static final FinanceAccount KB_ACCOUNT =
			new FinanceAccount("004", "국민은행", "0041456503815897", "국민 수시입출금", "1", 3_000_000L, "KRW");
	private static final FinanceAccount DEPOSIT_ACCOUNT =
			new FinanceAccount("020", "우리은행", "0204667768182760", "우리 정기예금", "2", 8_003_477L, "KRW");
	private static final FinanceAccount SHINHAN_ACCOUNT =
			new FinanceAccount("088", "신한은행", "0880680068408149", "신한 수시입출금", "1", 125_000L, "KRW");
	private static final FinanceCard SHINHAN_CARD = new FinanceCard(
			"1005872701650761", "725", "1005-x", "1005", "신한카드", "신한 딥디저트 카드",
			"20310910", "0880680068408149", "1"
	);

	@Mock
	private UserRepository userRepository;

	@Mock
	private FinanceAccountClient financeAccountClient;

	@Mock
	private FinanceCardClient financeCardClient;

	@Mock
	private AssetSyncService assetSyncService;

	@InjectMocks
	private LinkCandidateService linkCandidateService;

	private User user;

	@BeforeEach
	void setUp() {
		user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
	}

	@Test
	void 금융망_목록을_동기화한_뒤_KeyFin_ID와_관리_여부를_담아_반환한다() {
		user.connectFinance(FIN_USER_KEY);
		List<FinanceAccount> financeAccounts = List.of(KB_ACCOUNT, DEPOSIT_ACCOUNT, SHINHAN_ACCOUNT);
		List<FinanceCard> financeCards = List.of(SHINHAN_CARD);
		Account kb = Account.sync(user, "0041456503815897", "004", "국민은행", 3_000_000L, LocalDateTime.now());
		ReflectionTestUtils.setField(kb, "id", 3L);
		Account shinhan = Account.sync(user, "0880680068408149", "088", "신한은행", 125_000L, LocalDateTime.now());
		ReflectionTestUtils.setField(shinhan, "id", 4L);
		shinhan.link();
		Card card = Card.sync(user, "1005872701650761", "725", "1005", "신한 딥디저트 카드", shinhan);
		ReflectionTestUtils.setField(card, "id", 7L);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(financeAccountClient.findAccounts(FIN_USER_KEY)).willReturn(financeAccounts);
		given(financeCardClient.findCards(FIN_USER_KEY)).willReturn(financeCards);
		given(assetSyncService.sync(USER_ID, financeAccounts, financeCards)).willReturn(new SyncedAssets(
				Map.of("0041456503815897", kb, "0880680068408149", shinhan),
				Map.of("1005872701650761", card)
		));

		LinkCandidatesResponse response = linkCandidateService.getCandidates(USER_ID);

		assertThat(response.accounts())
				.extracting(
						LinkCandidatesResponse.AccountCandidate::id,
						LinkCandidatesResponse.AccountCandidate::finAccountNo,
						LinkCandidatesResponse.AccountCandidate::balance,
						LinkCandidatesResponse.AccountCandidate::managed
				)
				.containsExactly(
						Tuple.tuple(3L, "0041456503815897", 3_000_000L, false),
						Tuple.tuple(4L, "0880680068408149", 125_000L, true)
				);
		assertThat(response.accounts().get(0).bankName()).isEqualTo("국민은행");
		assertThat(response.cards())
				.extracting(
						LinkCandidatesResponse.CardCandidate::id,
						LinkCandidatesResponse.CardCandidate::cardNo,
						LinkCandidatesResponse.CardCandidate::issuerName,
						LinkCandidatesResponse.CardCandidate::withdrawalAccountNo,
						LinkCandidatesResponse.CardCandidate::managed
				)
				.containsExactly(Tuple.tuple(7L, "1005872701650761", "신한카드", "0880680068408149", false));
		verify(assetSyncService).sync(USER_ID, financeAccounts, financeCards);
	}

	@Test
	void 금융망_계좌와_카드가_없으면_빈_목록을_반환한다() {
		user.connectFinance(FIN_USER_KEY);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(financeAccountClient.findAccounts(FIN_USER_KEY)).willReturn(List.of());
		given(financeCardClient.findCards(FIN_USER_KEY)).willReturn(List.of());
		given(assetSyncService.sync(USER_ID, List.of(), List.of()))
				.willReturn(new SyncedAssets(Map.of(), Map.of()));

		LinkCandidatesResponse response = linkCandidateService.getCandidates(USER_ID);

		assertThat(response.accounts()).isEmpty();
		assertThat(response.cards()).isEmpty();
	}

	@Test
	void 금융망에_연결되지_않은_사용자는_금융망을_호출하지_않고_거절한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));

		assertBusinessError(
				LinkErrorCode.FINANCE_NOT_CONNECTED,
				() -> linkCandidateService.getCandidates(USER_ID)
		);
		verifyNoInteractions(financeAccountClient, financeCardClient, assetSyncService);
	}

	@Test
	void 탈퇴했거나_존재하지_않는_사용자는_거절한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertBusinessError(
				UserErrorCode.USER_NOT_FOUND,
				() -> linkCandidateService.getCandidates(USER_ID)
		);
		verifyNoInteractions(financeAccountClient, financeCardClient, assetSyncService);
	}

	private void assertBusinessError(ErrorCode expectedErrorCode, Runnable action) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(expectedErrorCode);
	}
}
