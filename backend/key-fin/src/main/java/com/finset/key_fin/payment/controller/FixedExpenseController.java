package com.finset.key_fin.payment.controller;

import static org.springframework.http.HttpStatus.CREATED;

import java.util.List;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.request.FixedExpenseCardRequest;
import com.finset.key_fin.payment.dto.request.FixedExpenseRequest;
import com.finset.key_fin.payment.dto.response.FixedExpenseIdResponse;
import com.finset.key_fin.payment.dto.response.FixedExpenseResponse;
import com.finset.key_fin.payment.service.FixedExpenseService;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/v1/fixed-expenses")
@RequiredArgsConstructor
public class FixedExpenseController implements FixedExpenseControllerDocs {

	private final FixedExpenseService fixedExpenseService;

	@PostMapping
	@ResponseStatus(CREATED)
	@Override
	public BaseResponse<FixedExpenseIdResponse> register(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody FixedExpenseRequest request
	) {
		return BaseResponse.ok(fixedExpenseService.register(userId, request));
	}

	@GetMapping
	@Override
	public BaseResponse<List<FixedExpenseResponse>> list(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(fixedExpenseService.list(userId));
	}

	@PutMapping("/{fixedExpenseId}")
	@Override
	public BaseResponse<FixedExpenseIdResponse> update(
			@AuthenticationPrincipal Long userId,
			@PathVariable long fixedExpenseId,
			@Valid @RequestBody FixedExpenseRequest request
	) {
		return BaseResponse.ok(fixedExpenseService.update(userId, fixedExpenseId, request));
	}

	@PatchMapping("/{fixedExpenseId}/card")
	@Override
	public BaseResponse<FixedExpenseIdResponse> assignCard(
			@AuthenticationPrincipal Long userId,
			@PathVariable long fixedExpenseId,
			@Valid @RequestBody FixedExpenseCardRequest request
	) {
		return BaseResponse.ok(fixedExpenseService.assignCard(userId, fixedExpenseId, request.cardId()));
	}

	@DeleteMapping("/{fixedExpenseId}")
	@Override
	public BaseResponse<Void> delete(
			@AuthenticationPrincipal Long userId,
			@PathVariable long fixedExpenseId
	) {
		fixedExpenseService.delete(userId, fixedExpenseId);
		return BaseResponse.ok();
	}
}
