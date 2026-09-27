package com.finset.key_fin.coaching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record SpendingRow(
		@JsonProperty("envelope") String envelope,
		@JsonProperty("total_krw") long totalKrw,
		@JsonProperty("count") int count
) {
}
