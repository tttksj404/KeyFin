package com.finset.key_fin.coaching.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import com.finset.key_fin.coaching.dto.CoachFeedbackResponse;
import com.finset.key_fin.coaching.service.CoachingAlertFeedbackStore;
import com.finset.key_fin.global.base.BaseResponse;

import lombok.RequiredArgsConstructor;

@RestController
@RequiredArgsConstructor
public class CoachingAlertFeedbackController implements CoachingAlertFeedbackControllerDocs {

	private final CoachingAlertFeedbackStore store;

	@Override
	@GetMapping(value = "/api/v1/notifications/{notificationId}/coach-feedback", produces = APPLICATION_JSON_VALUE)
	public BaseResponse<CoachFeedbackResponse> feedback(
			@AuthenticationPrincipal Long userId,
			@PathVariable long notificationId
	) {
		return BaseResponse.ok(store.find(userId, notificationId));
	}
}
