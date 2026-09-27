package com.finset.key_fin.payment.controller;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.response.TransferApproveResponse;
import com.finset.key_fin.payment.dto.response.TransferDetailResponse;
import com.finset.key_fin.payment.dto.response.TransferListResponse;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.service.TransferService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/v1/transfers")
@RequiredArgsConstructor
public class TransferController implements TransferControllerDocs {

	private final TransferService transferService;

	@GetMapping
	@Override
	public BaseResponse<TransferListResponse> list(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) TransferStatus status,
			@RequestParam(required = false) String month,
			@RequestParam(required = false) Long cursor,
			@RequestParam(required = false) Integer size
	) {
		return BaseResponse.ok(transferService.list(userId, status, month, cursor, size));
	}

	@GetMapping("/{transferId}")
	@Override
	public BaseResponse<TransferDetailResponse> detail(
			@AuthenticationPrincipal Long userId,
			@PathVariable long transferId
	) {
		return BaseResponse.ok(transferService.detail(userId, transferId));
	}

	@PostMapping("/{transferId}/approve")
	@Override
	public BaseResponse<TransferApproveResponse> approve(
			@AuthenticationPrincipal Long userId,
			@PathVariable long transferId
	) {
		return BaseResponse.ok(transferService.approve(userId, transferId));
	}

	@PostMapping("/{transferId}/postpone")
	@Override
	public BaseResponse<Void> postpone(
			@AuthenticationPrincipal Long userId,
			@PathVariable long transferId
	) {
		transferService.postpone(userId, transferId);
		return BaseResponse.ok();
	}
}
