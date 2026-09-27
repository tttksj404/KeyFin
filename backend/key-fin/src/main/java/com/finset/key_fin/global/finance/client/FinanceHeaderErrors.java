package com.finset.key_fin.global.finance.client;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class FinanceHeaderErrors {

	private static final Logger log = LoggerFactory.getLogger(FinanceHeaderErrors.class);

	private FinanceHeaderErrors() {
	}

	public static RuntimeException map(String responseCode) {
		log.warn("금융망 Header API 오류 응답: responseCode={}", responseCode);
		if (FinanceResponseCode.HEADER_USER_KEY_INVALID.matches(responseCode)) {
			return new BusinessException(FinanceErrorCode.USER_KEY_INVALID);
		}
		if (FinanceResponseCode.HEADER_API_KEY_INVALID.matches(responseCode)) {
			return new BusinessException(FinanceErrorCode.CONFIGURATION_ERROR);
		}
		if (FinanceResponseCode.HEADER_TRANSACTION_NO_DUPLICATED.matches(responseCode)
				|| FinanceResponseCode.UNKNOWN_ERROR.matches(responseCode)) {
			return new RetryableFinanceException(null);
		}
		return new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
	}
}
