package com.finset.key_fin.global.finance.client;

import com.finset.key_fin.global.finance.config.FinanceProperties;
import com.finset.key_fin.global.finance.dto.request.FinanceRequestHeader;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.ThreadLocalRandom;

@Component
public class FinanceHeaderFactory {

	static final String INSTITUTION_CODE = "00100";
	static final String FINTECH_APP_NO = "001";
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyyMMdd");
	private static final DateTimeFormatter TIME_FORMAT = DateTimeFormatter.ofPattern("HHmmss");
	private static final int SEQUENCE_BOUND = 1_000_000;

	private final FinanceProperties properties;
	private final Clock clock;

	@Autowired
	public FinanceHeaderFactory(FinanceProperties properties) {
		this(properties, Clock.system(KST));
	}

	public FinanceHeaderFactory(FinanceProperties properties, Clock clock) {
		this.properties = properties;
		this.clock = clock.withZone(KST);
	}

	public FinanceRequestHeader create(String apiName, String userKey) {
		return create(apiName, userKey, newTransactionUniqueNo());
	}

	/** 멱등 재시도용 — 미리 채번해 저장한 기관거래고유번호로 헤더를 만든다(이체). */
	public FinanceRequestHeader create(String apiName, String userKey, String transactionUniqueNo) {
		requireText(apiName, "금융망 API 이름");
		requireText(userKey, "금융망 사용자 키");
		requireText(transactionUniqueNo, "기관거래고유번호");
		LocalDateTime now = LocalDateTime.now(clock);
		return new FinanceRequestHeader(
				apiName,
				DATE_FORMAT.format(now),
				TIME_FORMAT.format(now),
				INSTITUTION_CODE,
				FINTECH_APP_NO,
				apiName,
				transactionUniqueNo,
				properties.apiKey(),
				userKey
		);
	}

	public String newTransactionUniqueNo() {
		LocalDateTime now = LocalDateTime.now(clock);
		int sequence = ThreadLocalRandom.current().nextInt(SEQUENCE_BOUND);
		return DATE_FORMAT.format(now) + TIME_FORMAT.format(now) + String.format("%06d", sequence);
	}

	private static void requireText(String value, String name) {
		if (value == null || value.isBlank()) {
			throw new IllegalArgumentException(name + "은 비어 있을 수 없습니다.");
		}
	}
}
