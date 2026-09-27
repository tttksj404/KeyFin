package com.finset.key_fin.link.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.ErrorCode;
import com.finset.key_fin.link.dto.response.FinanceConnectResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
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

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class FinanceConnectWriterTest {

	private static final long USER_ID = 1L;
	private static final String FIN_USER_KEY = "finance-user-key";

	@Mock
	private UserRepository userRepository;

	@InjectMocks
	private FinanceConnectWriter financeConnectWriter;

	private User user;

	@BeforeEach
	void setUp() {
		user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
	}

	@Test
	void 금융망_사용자_키를_연결한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(userRepository.existsByFinUserKeyAndIdNot(FIN_USER_KEY, USER_ID)).willReturn(false);

		FinanceConnectResponse response = financeConnectWriter.connect(USER_ID, FIN_USER_KEY);

		assertThat(response.connected()).isTrue();
		assertThat(user.getFinUserKey()).isEqualTo(FIN_USER_KEY);
	}

	@Test
	void 같은_금융망_회원과의_재연결은_성공한다() {
		user.connectFinance(FIN_USER_KEY);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(userRepository.existsByFinUserKeyAndIdNot(FIN_USER_KEY, USER_ID)).willReturn(false);

		FinanceConnectResponse response = financeConnectWriter.connect(USER_ID, FIN_USER_KEY);

		assertThat(response.connected()).isTrue();
		assertThat(user.getFinUserKey()).isEqualTo(FIN_USER_KEY);
	}

	@Test
	void 다른_계정이_사용하는_금융망_회원은_연결할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(userRepository.existsByFinUserKeyAndIdNot(FIN_USER_KEY, USER_ID)).willReturn(true);

		assertBusinessError(
				LinkErrorCode.FINANCE_MEMBER_ALREADY_LINKED,
				() -> financeConnectWriter.connect(USER_ID, FIN_USER_KEY)
		);
		assertThat(user.isFinanceConnected()).isFalse();
	}

	@Test
	void 이미_연결된_사용자를_다른_금융망_회원으로_변경할_수_없다() {
		user.connectFinance("existing-finance-user-key");
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(userRepository.existsByFinUserKeyAndIdNot(FIN_USER_KEY, USER_ID)).willReturn(false);

		assertBusinessError(
				UserErrorCode.FINANCE_CONNECTION_CONFLICT,
				() -> financeConnectWriter.connect(USER_ID, FIN_USER_KEY)
		);
		assertThat(user.getFinUserKey()).isEqualTo("existing-finance-user-key");
	}

	@Test
	void 저장_시점에_사용자가_사라지면_연결할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertBusinessError(
				UserErrorCode.USER_NOT_FOUND,
				() -> financeConnectWriter.connect(USER_ID, FIN_USER_KEY)
		);
	}

	private void assertBusinessError(ErrorCode expectedErrorCode, Runnable action) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(expectedErrorCode);
	}
}
