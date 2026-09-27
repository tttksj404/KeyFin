package com.finset.key_fin.payment.dto.response;

public record FinanceTransferResult(Status status, String responseCode) {

	public static final FinanceTransferResult EXECUTED = new FinanceTransferResult(Status.EXECUTED, "H0000");
	public static final FinanceTransferResult ALREADY_PROCESSED = new FinanceTransferResult(Status.ALREADY_PROCESSED, "H1007");

	public boolean isSuccess() {
		return status == Status.EXECUTED || status == Status.ALREADY_PROCESSED;
	}

	public enum Status {
		EXECUTED,
		/** 같은 기관거래고유번호로 이미 처리됨(H1007) — 응답 유실 후 재시도에서 성공으로 간주. */
		ALREADY_PROCESSED,
		INSUFFICIENT_BALANCE,
		BANK_LIMIT_EXCEEDED
	}
}
