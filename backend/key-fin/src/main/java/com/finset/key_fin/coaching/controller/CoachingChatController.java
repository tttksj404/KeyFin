package com.finset.key_fin.coaching.controller;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import java.nio.charset.StandardCharsets;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.finset.key_fin.coaching.dto.ChatHistoryResponse;
import com.finset.key_fin.coaching.dto.ChatReply;
import com.finset.key_fin.coaching.dto.ChatRequest;
import com.finset.key_fin.coaching.service.CoachingChatService;
import com.finset.key_fin.global.base.BaseResponse;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/v1/coaching")
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
public class CoachingChatController implements CoachingChatControllerDocs {

	private final CoachingChatService coachingChatService;

	@PostMapping("/chat")
	@Override
	public BaseResponse<ChatReply> chat(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody ChatRequest request
	) {
		return BaseResponse.ok(coachingChatService.chat(userId, request.message()));
	}

	@GetMapping("/chat")
	@Override
	public BaseResponse<ChatHistoryResponse> history(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(coachingChatService.history(userId));
	}

	@PostMapping("/chat/reset")
	public BaseResponse<Void> reset(@AuthenticationPrincipal Long userId) {
		coachingChatService.reset(userId);
		return BaseResponse.ok();
	}

	@GetMapping(value = "/charts/{chartId}/html", produces = MediaType.TEXT_HTML_VALUE)
	@Override
	public ResponseEntity<String> chartHtml(
			@AuthenticationPrincipal Long userId,
			@PathVariable String chartId
	) {
		return ResponseEntity.ok()
				.contentType(new MediaType(MediaType.TEXT_HTML, StandardCharsets.UTF_8))
				.body(coachingChatService.chartHtml(userId, chartId));
	}
}
