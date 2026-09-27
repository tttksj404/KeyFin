package com.finset.key_fin.item.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.item.dto.request.ItemEquipmentUpdateRequest;
import com.finset.key_fin.item.dto.response.AvatarEquipmentResponse;
import com.finset.key_fin.item.dto.response.UserItemResponse;
import com.finset.key_fin.item.service.ItemService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/items")
@RequiredArgsConstructor
public class ItemController implements ItemControllerDocs {
	private final ItemService itemService;

	@GetMapping(produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<List<UserItemResponse>> getItems(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) String slotType
	) {
		return BaseResponse.ok(itemService.getItems(userId, slotType));
	}

	@PatchMapping(value = "/{userItemId}", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<AvatarEquipmentResponse> updateEquipment(
			@AuthenticationPrincipal Long userId,
			@Positive @PathVariable long userItemId,
			@Valid @RequestBody ItemEquipmentUpdateRequest request
	) {
		return BaseResponse.ok(itemService.updateEquipment(userId, userItemId, request.equipped()));
	}
}
