package com.finset.key_fin.account.entity;

import com.finset.key_fin.user.entity.User;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;

class AccountTest {

	private static final User USER = User.create("qwer@qwer.com", "encoded-password", "김예린");

	@Test
	void 금융망_계좌를_잔액_스냅샷과_함께_생성한다() {
		LocalDateTime updatedAt = LocalDateTime.of(2026, 9, 11, 12, 30);
		Account account = Account.sync(
				USER, "0041456503815897", "004", "국민은행", 3_000_000L, updatedAt);

		assertThat(account.getBankName()).isEqualTo("국민은행");
		assertThat(account.getBalance()).isEqualTo(3_000_000L);
		assertThat(account.getBalanceUpdatedAt()).isEqualTo(updatedAt);
		assertThat(account.isManaged()).isFalse();
	}

	@Test
	void 잔액_스냅샷을_최신_금융망_값으로_갱신한다() {
		Account account = Account.sync(
				USER, "0041456503815897", "004", "국민은행", 3_000_000L,
				LocalDateTime.of(2026, 9, 11, 12, 30));
		LocalDateTime updatedAt = LocalDateTime.of(2026, 9, 11, 13, 30);

		account.updateBalanceSnapshot("KB국민은행", 2_850_000L, updatedAt);

		assertThat(account.getBankName()).isEqualTo("KB국민은행");
		assertThat(account.getBalance()).isEqualTo(2_850_000L);
		assertThat(account.getBalanceUpdatedAt()).isEqualTo(updatedAt);
	}

	@Test
	void 잔액_확인_시각은_필수다() {
		assertThatNullPointerException().isThrownBy(() -> Account.sync(
				USER, "0041456503815897", "004", "국민은행", 3_000_000L, null));
	}

	@Test
	void 수입_계좌로_지정하고_해제한다() {
		Account account = Account.sync(
				USER, "0041456503815897", "004", "국민은행", 3_000_000L, LocalDateTime.now());

		account.designateAsIncome();
		assertThat(account.isIncome()).isTrue();

		account.removeIncomeDesignation();
		assertThat(account.isIncome()).isFalse();
	}
}
