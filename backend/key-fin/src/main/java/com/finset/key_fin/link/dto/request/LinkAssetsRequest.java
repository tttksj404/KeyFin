package com.finset.key_fin.link.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import java.util.List;

public record LinkAssetsRequest(
		@Schema(description = "연결할 KeyFin 계좌 ID 목록(후보 목록의 accounts[].id)", example = "[3, 4]")
		@Size(max = 50, message = "계좌는 한 번에 50개까지 연결할 수 있습니다.")
		List<@NotNull(message = "계좌 ID는 비어 있을 수 없습니다.")
		     @Positive(message = "계좌 ID는 양수여야 합니다.") Long> accountIds,
		@Schema(description = "연결할 KeyFin 카드 ID 목록(후보 목록의 cards[].id)", example = "[7]")
		@Size(max = 50, message = "카드는 한 번에 50개까지 연결할 수 있습니다.")
		List<@NotNull(message = "카드 ID는 비어 있을 수 없습니다.")
		     @Positive(message = "카드 ID는 양수여야 합니다.") Long> cardIds
) {

	public List<Long> accountIdsOrEmpty() {
		return accountIds == null ? List.of() : accountIds;
	}

	public List<Long> cardIdsOrEmpty() {
		return cardIds == null ? List.of() : cardIds;
	}

	public boolean isEmpty() {
		return accountIdsOrEmpty().isEmpty() && cardIdsOrEmpty().isEmpty();
	}
}
