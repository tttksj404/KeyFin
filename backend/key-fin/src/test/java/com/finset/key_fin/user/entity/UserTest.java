package com.finset.key_fin.user.entity;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class UserTest {

	@Test
	void 회원을_소프트_삭제한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		LocalDateTime deletedAt = LocalDateTime.of(2026, 9, 17, 10, 0);

		user.softDelete(deletedAt);

		assertThat(user.isDeleted()).isTrue();
		assertThat(user.getDeletedAt()).isEqualTo(deletedAt);
	}

	private static final String FIN_USER_KEY = "cf1d49ba-663b-495d-9227-fc2643aa7c5e";

	@Test
	void createsUserWithoutFinanceConnection() {
		User user = createUser();

		assertThat(user.isFinanceConnected()).isFalse();
		assertThat(user.getFinUserKey()).isNull();
	}

	@Test
	void connectsFinanceMember() {
		User user = createUser();

		user.connectFinance(FIN_USER_KEY);

		assertThat(user.isFinanceConnected()).isTrue();
		assertThat(user.getFinUserKey()).isEqualTo(FIN_USER_KEY);
	}

	@Test
	void treatsSameFinanceConnectionAsIdempotent() {
		User user = createUser();
		user.connectFinance(FIN_USER_KEY);

		user.connectFinance(FIN_USER_KEY);

		assertThat(user.getFinUserKey()).isEqualTo(FIN_USER_KEY);
	}

	@Test
	void rejectsReplacingExistingFinanceConnection() {
		User user = createUser();
		user.connectFinance(FIN_USER_KEY);

		assertThatThrownBy(() -> user.connectFinance("different-fin-user-key"))
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(UserErrorCode.FINANCE_CONNECTION_CONFLICT);
	}

	@Test
	void rejectsBlankFinanceUserKey() {
		User user = createUser();

		assertThatIllegalArgumentException()
				.isThrownBy(() -> user.connectFinance(" "))
				.withMessage("금융망 사용자 키는 비어 있을 수 없습니다.");
	}

	private User createUser() {
		return User.create("qwer@qwer.com", "encoded-password", "김예린");
	}
}
