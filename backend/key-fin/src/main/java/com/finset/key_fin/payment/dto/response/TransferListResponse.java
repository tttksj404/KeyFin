package com.finset.key_fin.payment.dto.response;

import java.util.List;

public record TransferListResponse(
		List<TransferResponse> items,
		Long nextCursor
) {
}
