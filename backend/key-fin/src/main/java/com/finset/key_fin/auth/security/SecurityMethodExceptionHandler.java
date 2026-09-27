package com.finset.key_fin.auth.security;

import com.finset.key_fin.auth.exception.AuthErrorCode;
import com.finset.key_fin.global.base.BaseResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Order(Ordered.HIGHEST_PRECEDENCE)
@RestControllerAdvice
public class SecurityMethodExceptionHandler {

	@ExceptionHandler(AccessDeniedException.class)
	public ResponseEntity<BaseResponse<Void>> handleAccessDeniedException(
			AccessDeniedException exception
	) {
		AuthErrorCode errorCode = AuthErrorCode.ACCESS_DENIED;
		return ResponseEntity.status(errorCode.getHttpStatus())
				.body(BaseResponse.fail(errorCode.getCode(), errorCode.getMessage()));
	}
}
