package com.finset.key_fin.account.service;

import com.finset.key_fin.account.dto.response.AccountListResponse;
import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
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

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class AccountServiceTest {

	private static final long USER_ID = 1L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private AccountRepository accountRepository;

	@InjectMocks
	private AccountService accountService;

	private User user;

	@BeforeEach
	void setUp() {
		user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
	}

	@Test
	void 관리_중인_계좌를_ID_오름차순으로_조회한다() {
		LocalDateTime updatedAt = LocalDateTime.of(2026, 9, 11, 14, 30);
		Account account = Account.sync(
				user, "0010011073486799", "001", "한국은행", 1_500_000L, updatedAt);
		ReflectionTestUtils.setField(account, "id", 3L);
		ReflectionTestUtils.setField(account, "alias", "생활비");
		account.link();
		ReflectionTestUtils.setField(account, "income", true);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(USER_ID))
				.willReturn(List.of(account));

		AccountListResponse response = accountService.getManagedAccounts(USER_ID);

		assertThat(response.items()).hasSize(1);
		assertThat(response.items().getFirst())
				.extracting("id", "finAccountNo", "bankName", "alias", "income", "managed", "balance", "balanceUpdatedAt")
				.containsExactly(3L, "0010011073486799", "한국은행", "생활비", true, true, 1_500_000L, updatedAt);
	}

	@Test
	void 관리_중인_계좌가_없으면_빈_목록을_반환한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(USER_ID)).willReturn(List.of());

		AccountListResponse response = accountService.getManagedAccounts(USER_ID);

		assertThat(response.items()).isEmpty();
	}

	@Test
	void 탈퇴했거나_없는_사용자는_계좌를_조회할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> accountService.getManagedAccounts(USER_ID))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(accountRepository);
	}

	@Test
	void 기존_수입_계좌를_해제하고_선택한_계좌를_수입_계좌로_지정한다() {
		Account previous = account(3L, true, true);
		Account selected = account(4L, true, false);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findByIdAndUserId(4L, USER_ID)).willReturn(Optional.of(selected));
		given(accountRepository.findAllByUserIdAndIncomeTrue(USER_ID)).willReturn(List.of(previous));

		accountService.designateIncomeAccount(USER_ID, 4L);

		assertThat(previous.isIncome()).isFalse();
		assertThat(selected.isIncome()).isTrue();
	}

	@Test
	void 이미_수입_계좌이면_추가_변경_없이_성공한다() {
		Account selected = account(3L, true, true);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findByIdAndUserId(3L, USER_ID)).willReturn(Optional.of(selected));

		accountService.designateIncomeAccount(USER_ID, 3L);

		assertThat(selected.isIncome()).isTrue();
		verify(accountRepository).findByIdAndUserId(3L, USER_ID);
	}

	@Test
	void 본인_소유가_아닌_계좌는_지정할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findByIdAndUserId(99L, USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> accountService.designateIncomeAccount(USER_ID, 99L))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode().getCode()).isEqualTo("ACCOUNT_001"));
	}

	@Test
	void 관리하지_않는_계좌는_수입_계좌로_지정할_수_없다() {
		Account selected = account(3L, false, false);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findByIdAndUserId(3L, USER_ID)).willReturn(Optional.of(selected));

		assertThatThrownBy(() -> accountService.designateIncomeAccount(USER_ID, 3L))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode().getCode()).isEqualTo("ACCOUNT_002"));
	}

	private Account account(long id, boolean managed, boolean income) {
		Account account = Account.sync(
				user, "004145650381%04d".formatted(id), "004", "국민은행", 1_500_000L, LocalDateTime.now());
		ReflectionTestUtils.setField(account, "id", id);
		if (managed) {
			account.link();
		}
		if (income) {
			account.designateAsIncome();
		}
		return account;
	}
}
