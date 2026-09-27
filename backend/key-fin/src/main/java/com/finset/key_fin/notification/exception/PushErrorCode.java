package com.finset.key_fin.notification.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum PushErrorCode implements ErrorCode {
	REGISTRATION_CONFLICT(HttpStatus.CONFLICT, "PUSH_001", "기기 정보가 변경 중입니다. 다시 시도해 주세요.");
	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
