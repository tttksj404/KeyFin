package com.finset.key_fin.global.exception;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class BusinessExceptionTest {

	@Test
	void retainsErrorCodeAndPublicMessage() {
		ErrorCode errorCode = mock(ErrorCode.class);
		when(errorCode.getMessage()).thenReturn("사용자를 찾을 수 없습니다.");

		BusinessException exception = new BusinessException(errorCode);

		assertThat(exception.getErrorCode()).isSameAs(errorCode);
		assertThat(exception).hasMessage("사용자를 찾을 수 없습니다.").hasNoCause();
	}

	@Test
	void retainsCauseWithoutReplacingPublicMessage() {
		ErrorCode errorCode = mock(ErrorCode.class);
		when(errorCode.getMessage()).thenReturn("요청을 처리할 수 없습니다.");
		IllegalStateException cause = new IllegalStateException("internal database detail");

		BusinessException exception = new BusinessException(errorCode, cause);

		assertThat(exception.getErrorCode()).isSameAs(errorCode);
		assertThat(exception).hasMessage("요청을 처리할 수 없습니다.").hasCause(cause);
	}

	@Test
	void requiresErrorCodeInBothConstructors() {
		assertThatNullPointerException().isThrownBy(() -> new BusinessException(null));
		assertThatNullPointerException().isThrownBy(
				() -> new BusinessException(null, new IllegalStateException())
		);
	}
}
