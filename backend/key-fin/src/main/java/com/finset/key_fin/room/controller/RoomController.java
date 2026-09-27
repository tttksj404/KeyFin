package com.finset.key_fin.room.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.room.dto.response.RoomResponse;
import com.finset.key_fin.room.service.RoomService;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.room.dto.request.StickerRemovalRequest;
import com.finset.key_fin.room.dto.response.StickerRemovalResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/room")
@RequiredArgsConstructor
public class RoomController implements RoomControllerDocs {

	private final RoomService roomService;
	private final RoomStickerService stickerService;

	@GetMapping
	@Override
	public BaseResponse<RoomResponse> getRoom(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(roomService.getRoom(userId));
	}

	@PostMapping("/stickers/removals")
	@Override
	public BaseResponse<StickerRemovalResponse> removeSticker(@AuthenticationPrincipal Long userId,
			@Valid @RequestBody StickerRemovalRequest request) {
		return BaseResponse.ok(stickerService.remove(userId, request.userFurnitureId()));
	}
}
