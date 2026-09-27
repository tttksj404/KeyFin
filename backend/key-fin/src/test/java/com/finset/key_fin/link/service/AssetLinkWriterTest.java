package com.finset.key_fin.link.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.ErrorCode;
import com.finset.key_fin.link.dto.response.LinkAssetsResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class AssetLinkWriterTest {

	private static final long USER_ID = 1L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private AccountRepository accountRepository;

	@Mock
	private CardRepository cardRepository;

	@InjectMocks
	private AssetLinkWriter assetLinkWriter;

	private User user;
	private Account kbAccount;
	private Account shinhanAccount;
	private Card shinhanCard;

	@BeforeEach
	void setUp() {
		user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
		kbAccount = Account.sync(user, "0041456503815897", "004", "국민은행", 3_000_000L, LocalDateTime.now());
		ReflectionTestUtils.setField(kbAccount, "id", 3L);
		shinhanAccount = Account.sync(user, "0880680068408149", "088", "신한은행", 125_000L, LocalDateTime.now());
		ReflectionTestUtils.setField(shinhanAccount, "id", 4L);
		shinhanCard = Card.sync(user, "1005872701650761", "725", "1005", "신한 딥디저트 카드", shinhanAccount);
		ReflectionTestUtils.setField(shinhanCard, "id", 7L);
	}

	@Test
	void 선택한_계좌와_카드를_관리_대상으로_전환하고_건수를_반환한다() {
		given(accountRepository.findAllByIdInAndUserId(Set.of(3L, 4L), USER_ID))
				.willReturn(List.of(kbAccount, shinhanAccount));
		given(cardRepository.findAllByIdInAndUserId(Set.of(7L), USER_ID)).willReturn(List.of(shinhanCard));

		LinkAssetsResponse response = assetLinkWriter.link(USER_ID, Set.of(3L, 4L), Set.of(7L));

		assertThat(response.accounts()).isEqualTo(2);
		assertThat(response.cards()).isEqualTo(1);
		assertThat(kbAccount.isManaged()).isTrue();
		assertThat(shinhanAccount.isManaged()).isTrue();
		assertThat(shinhanCard.isManaged()).isTrue();
	}

	@Test
	void 이미_관리_중인_항목은_건수에서_제외한다() {
		kbAccount.link();
		given(accountRepository.findAllByIdInAndUserId(Set.of(3L, 4L), USER_ID))
				.willReturn(List.of(kbAccount, shinhanAccount));

		LinkAssetsResponse response = assetLinkWriter.link(USER_ID, Set.of(3L, 4L), Set.of());

		assertThat(response.accounts()).isEqualTo(1);
		assertThat(response.cards()).isZero();
		verifyNoInteractions(cardRepository);
	}

	@Test
	void 연결_해제된_항목을_다시_선택하면_관리_대상으로_복구된다() {
		shinhanCard.link();
		shinhanCard.unlink();
		given(cardRepository.findAllByIdInAndUserId(Set.of(7L), USER_ID)).willReturn(List.of(shinhanCard));

		LinkAssetsResponse response = assetLinkWriter.link(USER_ID, Set.of(), Set.of(7L));

		assertThat(response.cards()).isEqualTo(1);
		assertThat(shinhanCard.isManaged()).isTrue();
	}

	@Test
	void 본인_소유가_아닌_계좌_ID가_섞이면_전체를_거절한다() {
		given(accountRepository.findAllByIdInAndUserId(Set.of(3L, 999L), USER_ID)).willReturn(List.of(kbAccount));

		assertBusinessError(
				LinkErrorCode.ACCOUNT_NOT_FOUND,
				() -> assetLinkWriter.link(USER_ID, Set.of(3L, 999L), Set.of())
		);
		assertThat(kbAccount.isManaged()).isFalse();
	}

	@Test
	void 본인_소유가_아닌_카드_ID는_거절한다() {
		given(cardRepository.findAllByIdInAndUserId(Set.of(999L), USER_ID)).willReturn(List.of());

		assertBusinessError(
				LinkErrorCode.CARD_NOT_FOUND,
				() -> assetLinkWriter.link(USER_ID, Set.of(), Set.of(999L))
		);
	}

	@Test
	void 계좌_연결을_해제하면_관리_대상과_수입_계좌_지정이_함께_풀린다() {
		kbAccount.link();
		ReflectionTestUtils.setField(kbAccount, "income", true);
		given(accountRepository.findByIdAndUserId(3L, USER_ID)).willReturn(Optional.of(kbAccount));

		assetLinkWriter.unlinkAccount(USER_ID, 3L);

		assertThat(kbAccount.isManaged()).isFalse();
		assertThat(kbAccount.isIncome()).isFalse();
	}

	@Test
	void 본인_계좌가_아니면_해제할_수_없다() {
		given(accountRepository.findByIdAndUserId(10L, USER_ID)).willReturn(Optional.empty());

		assertBusinessError(LinkErrorCode.ACCOUNT_NOT_FOUND, () -> assetLinkWriter.unlinkAccount(USER_ID, 10L));
	}

	@Test
	void 카드_연결을_해제하면_관리_대상에서_제외된다() {
		shinhanCard.link();
		given(cardRepository.findByIdAndUserId(7L, USER_ID)).willReturn(Optional.of(shinhanCard));

		assetLinkWriter.unlinkCard(USER_ID, 7L);

		assertThat(shinhanCard.isManaged()).isFalse();
	}

	@Test
	void 본인_카드가_아니면_해제할_수_없다() {
		given(cardRepository.findByIdAndUserId(20L, USER_ID)).willReturn(Optional.empty());

		assertBusinessError(LinkErrorCode.CARD_NOT_FOUND, () -> assetLinkWriter.unlinkCard(USER_ID, 20L));
	}

	private void assertBusinessError(ErrorCode expectedErrorCode, Runnable action) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(expectedErrorCode);
	}
}
