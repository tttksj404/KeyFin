package com.finset.key_fin.notification.controller;

import java.util.UUID;
import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.notification.dto.request.PushDeviceRequest;
import com.finset.key_fin.notification.service.PushDeviceService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/me/push-devices")
@RequiredArgsConstructor
public class PushDeviceController implements PushDeviceControllerDocs {
	private final PushDeviceService service;

	@Override
	@PutMapping("/{installationId}")
	public BaseResponse<Void> register(@AuthenticationPrincipal Long userId,
			@PathVariable String installationId, @Valid @RequestBody PushDeviceRequest request) {
		service.register(userId, parseId(installationId), request);
		return BaseResponse.ok();
	}

	@Override
	@DeleteMapping("/{installationId}")
	public BaseResponse<Void> disconnect(@AuthenticationPrincipal Long userId, @PathVariable String installationId) {
		service.disconnect(userId, parseId(installationId));
		return BaseResponse.ok();
	}

	private UUID parseId(String value) {
		try {
			UUID id = UUID.fromString(value);
			if (id.toString().equalsIgnoreCase(value)) return id;
		} catch (IllegalArgumentException ignored) {
		}
		throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
	}
}
