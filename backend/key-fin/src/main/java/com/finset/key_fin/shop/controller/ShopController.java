package com.finset.key_fin.shop.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.shop.dto.request.ShopPurchaseRequest;
import com.finset.key_fin.shop.dto.response.ShopItemResponse;
import com.finset.key_fin.shop.dto.response.ShopPurchaseResponse;
import com.finset.key_fin.shop.service.ShopService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/shop")
@RequiredArgsConstructor
public class ShopController implements ShopControllerDocs {
	private final ShopService shopService;

	@GetMapping(produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<List<ShopItemResponse>> getItems(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) String itemCategory,
			@RequestParam(required = false) String slotType
	) {
		return BaseResponse.ok(shopService.getItems(userId, itemCategory, slotType));
	}

	@PostMapping(value = "/purchase", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<ShopPurchaseResponse> purchase(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody ShopPurchaseRequest request
	) {
		return BaseResponse.ok(shopService.purchase(userId, request.itemId()));
	}
}
