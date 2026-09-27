package com.finset.key_fin.global.finance.client;

import java.time.Duration;

public final class RetryableFinanceException extends RuntimeException {

	private final transient Duration retryAfter;

	public RetryableFinanceException(Duration retryAfter) {
		super("금융망 일시 장애 응답");
		this.retryAfter = retryAfter;
	}

	public Duration retryAfter() {
		return retryAfter;
	}
}
