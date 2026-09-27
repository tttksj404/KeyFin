package com.finset.key_fin.global.finance.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum FinanceErrorCode implements ErrorCode {

	MEMBER_NOT_FOUND(HttpStatus.NOT_FOUND, "FINANCE_001", "금융망에서 일치하는 사용자를 찾을 수 없습니다."),
	INVALID_RESPONSE(HttpStatus.BAD_GATEWAY, "FINANCE_002", "금융망 응답을 처리할 수 없습니다."),
	CONFIGURATION_ERROR(HttpStatus.BAD_GATEWAY, "FINANCE_003", "금융망 연동 설정을 확인할 수 없습니다."),
	SERVICE_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "FINANCE_004", "금융망 서비스를 일시적으로 이용할 수 없습니다."),
	USER_KEY_INVALID(HttpStatus.CONFLICT, "FINANCE_005", "금융망 연결이 유효하지 않습니다. 금융망을 다시 연결해 주세요.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
