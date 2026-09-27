package com.finset.key_fin.account.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum AccountErrorCode implements ErrorCode {

	ACCOUNT_NOT_FOUND(HttpStatus.NOT_FOUND, "ACCOUNT_001", "계좌를 찾을 수 없습니다."),
	ACCOUNT_NOT_MANAGED(HttpStatus.CONFLICT, "ACCOUNT_002", "관리 중인 계좌만 수입 계좌로 지정할 수 있습니다.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
