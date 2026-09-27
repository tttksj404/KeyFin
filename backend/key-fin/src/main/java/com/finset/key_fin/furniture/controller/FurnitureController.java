package com.finset.key_fin.furniture.controller;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;
import com.finset.key_fin.furniture.service.FurnitureService;
import com.finset.key_fin.global.base.BaseResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/furnitures")
@RequiredArgsConstructor
public class FurnitureController implements FurnitureControllerDocs {
	private final FurnitureService furnitureService;

	@GetMapping(produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<List<UserFurnitureResponse>> getFurnitures(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) String slotType
	) {
		return BaseResponse.ok(furnitureService.getFurnitures(userId, slotType));
	}

	@PutMapping(value = "/placements", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<List<UserFurnitureResponse>> updatePlacements(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody FurniturePlacementsUpdateRequest request
	) {
		return BaseResponse.ok(furnitureService.updatePlacements(userId, request));
	}

	@PatchMapping(value = "/{userFurnitureId}", consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<UserFurnitureResponse> updatePlacement(
			@AuthenticationPrincipal Long userId,
			@Positive @PathVariable long userFurnitureId,
			@Valid @RequestBody FurniturePlacementUpdateRequest request
	) {
		return BaseResponse.ok(furnitureService.updatePlacement(userId, userFurnitureId, request));
	}
}
