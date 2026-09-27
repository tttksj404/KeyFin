package com.finset.key_fin.coaching.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** FDT 원장 한 건. 필드 이름과 순서는 엔진의 필수 컬럼 계약을 따른다. */
public record FdtTransaction(
		@JsonProperty("user_id") String userId,
		@JsonProperty("transaction_id") String transactionId,
		@JsonProperty("source") String source,
		@JsonProperty("transaction_type") String transactionType,
		@JsonProperty("transaction_date") String transactionDate,
		@JsonProperty("transaction_time") String transactionTime,
		@JsonProperty("category") String category,
		@JsonProperty("subcategory") String subcategory,
		@JsonProperty("merchant") String merchant,
		@JsonProperty("merchant_id") String merchantId,
		@JsonProperty("amount_krw") long amountKrw,
		@JsonProperty("account_id") String accountId,
		@JsonProperty("card_id") String cardId,
		@JsonProperty("confirm_status") String confirmStatus,
		@JsonProperty("status") String status,
		@JsonProperty("exclude_tag") String excludeTag
) {
}
