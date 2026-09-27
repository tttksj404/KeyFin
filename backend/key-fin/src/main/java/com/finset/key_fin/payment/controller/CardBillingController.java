package com.finset.key_fin.payment.controller;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse;
import com.finset.key_fin.payment.service.CardBillingQueryService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/v1/cards")
@RequiredArgsConstructor
public class CardBillingController implements CardBillingControllerDocs {

	private final CardBillingQueryService cardBillingQueryService;

	@GetMapping("/billings")
	@Override
	public BaseResponse<CardBillingSummaryResponse> summary(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(cardBillingQueryService.summary(userId));
	}

	@GetMapping("/{cardId}/billings")
	@Override
	public BaseResponse<CardBillingDetailResponse> detail(
			@AuthenticationPrincipal Long userId,
			@PathVariable long cardId,
			@RequestParam(required = false) String from,
			@RequestParam(required = false) String to
	) {
		return BaseResponse.ok(cardBillingQueryService.detail(userId, cardId, from, to));
	}
}
