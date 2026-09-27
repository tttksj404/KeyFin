package com.finset.key_fin.global.finance.client;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;

import java.time.Duration;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Supplier;

@Component
public class FinanceRetryExecutor {

	private static final Logger log = LoggerFactory.getLogger(FinanceRetryExecutor.class);

	private final FinanceProperties properties;

	public FinanceRetryExecutor(FinanceProperties properties) {
		this.properties = properties;
	}

	public <T> T execute(String operation, Supplier<T> attempt) {
		long startedAt = System.nanoTime();
		Throwable lastCause = null;
		Duration retryAfter = null;

		for (int attemptNo = 1; attemptNo <= properties.maxAttempts(); attemptNo++) {
			try {
				return attempt.get();
			} catch (RetryableFinanceException exception) {
				lastCause = exception;
				retryAfter = exception.retryAfter();
			} catch (BusinessException exception) {
				throw exception;
			} catch (RestClientException exception) {
				lastCause = exception;
				retryAfter = null;
			}

			if (attemptNo < properties.maxAttempts()) {
				Duration delay = resolveRetryDelay(attemptNo, retryAfter);
				if (delay == null || exceedsRetryTimeLimit(startedAt, delay)) {
					break;
				}
				log.warn(
						"금융망 {} 재시도: 다음 시도={}/{}, 대기={}ms",
						operation,
						attemptNo + 1,
						properties.maxAttempts(),
						delay.toMillis()
				);
				waitBeforeRetry(delay);
			}
		}

		throw new BusinessException(FinanceErrorCode.SERVICE_UNAVAILABLE, lastCause);
	}

	private Duration resolveRetryDelay(int failedAttempt, Duration retryAfter) {
		if (retryAfter != null) {
			return retryAfter.compareTo(properties.retryMaxDelay()) <= 0 ? retryAfter : null;
		}

		long multiplier = 1L << Math.min(failedAttempt - 1, 30);
		Duration exponentialDelay;
		try {
			exponentialDelay = properties.retryBaseDelay().multipliedBy(multiplier);
		} catch (ArithmeticException exception) {
			exponentialDelay = properties.retryMaxDelay();
		}
		Duration delayCap = exponentialDelay.compareTo(properties.retryMaxDelay()) < 0
				? exponentialDelay
				: properties.retryMaxDelay();
		long delayCapMillis = delayCap.toMillis();
		if (delayCapMillis <= 0) {
			return Duration.ZERO;
		}
		return Duration.ofMillis(ThreadLocalRandom.current().nextLong(delayCapMillis + 1));
	}

	private boolean exceedsRetryTimeLimit(long startedAt, Duration delay) {
		Duration elapsed = Duration.ofNanos(System.nanoTime() - startedAt);
		return elapsed.plus(delay).compareTo(properties.retryTimeLimit()) >= 0;
	}

	private void waitBeforeRetry(Duration delay) {
		try {
			Thread.sleep(delay);
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			throw new BusinessException(FinanceErrorCode.SERVICE_UNAVAILABLE, exception);
		}
	}
}
