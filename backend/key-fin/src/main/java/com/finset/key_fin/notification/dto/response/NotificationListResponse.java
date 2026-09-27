package com.finset.key_fin.notification.dto.response;

import java.util.List;
import io.swagger.v3.oas.annotations.media.Schema;

public record NotificationListResponse(
		List<NotificationResponse> items,
		@Schema(description = "다음 페이지 cursor. 마지막 페이지면 null", nullable = true) Long nextCursor
) {
}
