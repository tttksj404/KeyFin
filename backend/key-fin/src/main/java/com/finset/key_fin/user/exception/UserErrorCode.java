package com.finset.key_fin.user.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum UserErrorCode implements ErrorCode {

	USER_NOT_FOUND(HttpStatus.NOT_FOUND, "USER_001", "사용자를 찾을 수 없습니다."),
	DUPLICATE_EMAIL(HttpStatus.CONFLICT, "USER_002", "이미 사용 중인 이메일입니다."),
	DELETED_USER(HttpStatus.CONFLICT, "USER_003", "탈퇴한 이메일은 다시 가입할 수 없습니다."),
	FINANCE_CONNECTION_CONFLICT(HttpStatus.CONFLICT, "USER_004", "이미 다른 금융망 사용자와 연결되어 있습니다."),
	INVALID_TRANSFER_LIMIT(HttpStatus.BAD_REQUEST, "USER_005", "이체 한도 설정이 올바르지 않습니다."),
	USER_SETTINGS_NOT_FOUND(HttpStatus.NOT_FOUND, "USER_006", "사용자 설정을 찾을 수 없습니다."),
	PASSWORD_MISMATCH(HttpStatus.UNAUTHORIZED, "USER_007", "현재 비밀번호가 올바르지 않습니다."),
	USER_PROFILE_NOT_FOUND(HttpStatus.NOT_FOUND, "USER_008", "사용자 프로필을 찾을 수 없습니다."),
	INVALID_QUIET_HOURS(HttpStatus.BAD_REQUEST, "USER_009", "방해금지 시작 시각과 종료 시각을 올바르게 입력해 주세요."),
	BUDGET_ANCHOR_LOCKED(HttpStatus.CONFLICT, "USER_010", "예산이 시작된 뒤에는 기준일을 바꿀 수 없어요."),
	INVALID_BUDGET_ANCHOR_DAY(HttpStatus.BAD_REQUEST, "USER_011", "예산 기준일은 1일부터 28일 사이여야 합니다.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
