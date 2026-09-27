package com.finset.key_fin.notification.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.notification.dto.response.NotificationListResponse;
import com.finset.key_fin.notification.service.NotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/notifications")
@RequiredArgsConstructor
public class NotificationController implements NotificationControllerDocs {
	private final NotificationService service;

	@Override
	@GetMapping(produces = APPLICATION_JSON_VALUE)
	public BaseResponse<NotificationListResponse> list(@AuthenticationPrincipal Long userId,
			@RequestParam(defaultValue = "false") boolean unreadOnly,
			@RequestParam(required = false) Long cursor, @RequestParam(required = false) Integer size) {
		return BaseResponse.ok(service.list(userId, unreadOnly, cursor, size));
	}

	@Override
	@PatchMapping(value = "/{notificationId}/read", produces = APPLICATION_JSON_VALUE)
	public BaseResponse<Void> markRead(@AuthenticationPrincipal Long userId, @PathVariable long notificationId) {
		service.markRead(userId, notificationId);
		return BaseResponse.ok();
	}
}
