package com.finset.key_fin.global.finance.client;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Set;

public final class FinanceHttpSupport {

	private static final Set<Integer> RETRYABLE_STATUS_CODES = Set.of(408, 429, 500, 502, 503, 504);

	private FinanceHttpSupport() {
	}

	public static boolean isRetryableStatus(HttpStatusCode statusCode) {
		return RETRYABLE_STATUS_CODES.contains(statusCode.value());
	}

	public static RetryableFinanceException retryableResponse(HttpHeaders headers) {
		return new RetryableFinanceException(parseRetryAfter(headers.getFirst(HttpHeaders.RETRY_AFTER)));
	}

	public static JsonNode readTree(ObjectMapper objectMapper, String body) {
		if (body == null || body.isBlank()) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
		}
		try {
			return objectMapper.readTree(body);
		} catch (JacksonException exception) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE, exception);
		}
	}

	public static <T> T convert(ObjectMapper objectMapper, JsonNode root, Class<T> type) {
		try {
			return objectMapper.treeToValue(root, type);
		} catch (JacksonException exception) {
			throw new BusinessException(FinanceErrorCode.INVALID_RESPONSE, exception);
		}
	}

	public static String textOrNull(JsonNode node) {
		if (node.isMissingNode() || node.isNull() || !node.isTextual() || node.asText().isBlank()) {
			return null;
		}
		return node.asText();
	}

	public static String headerResponseCode(JsonNode root) {
		String responseCode = textOrNull(root.path("Header").path("responseCode"));
		if (responseCode == null) {
			responseCode = textOrNull(root.path("responseCode"));
		}
		return responseCode;
	}

	public static Duration parseRetryAfter(String value) {
		if (value == null || value.isBlank()) {
			return null;
		}
		try {
			long seconds = Long.parseLong(value.trim());
			return seconds < 0 ? null : Duration.ofSeconds(seconds);
		} catch (NumberFormatException ignored) {
			try {
				Instant retryAt = ZonedDateTime.parse(value.trim(), DateTimeFormatter.RFC_1123_DATE_TIME).toInstant();
				Duration delay = Duration.between(Instant.now(), retryAt);
				return delay.isNegative() ? Duration.ZERO : delay;
			} catch (DateTimeParseException exception) {
				return null;
			}
		}
	}
}
