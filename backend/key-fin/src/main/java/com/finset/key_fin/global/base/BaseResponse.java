package com.finset.key_fin.global.base;

public record BaseResponse<T>(
		boolean success,
		String code,
		String message,
		T data
) {

	public static <T> BaseResponse<T> ok(T data) {
		return new BaseResponse<>(true, "SUCCESS", "요청이 성공했습니다.", data);
	}

	public static BaseResponse<Void> ok() {
		return ok(null);
	}

	public static BaseResponse<Void> fail(String code, String message) {
		return new BaseResponse<>(false, code, message, null);
	}
}
