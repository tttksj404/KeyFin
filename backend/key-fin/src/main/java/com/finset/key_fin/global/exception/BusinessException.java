package com.finset.key_fin.global.exception;

import lombok.Getter;

import java.util.Objects;

@Getter
public class BusinessException extends RuntimeException {

	private final ErrorCode errorCode;

	public BusinessException(ErrorCode errorCode) {
		super(Objects.requireNonNull(errorCode, "errorCode must not be null").getMessage());
		this.errorCode = errorCode;
	}

	public BusinessException(ErrorCode errorCode, Throwable cause) {
		super(Objects.requireNonNull(errorCode, "errorCode must not be null").getMessage(), cause);
		this.errorCode = errorCode;
	}
}
