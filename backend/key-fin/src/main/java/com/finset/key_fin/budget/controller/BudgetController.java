package com.finset.key_fin.budget.controller;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest;
import com.finset.key_fin.budget.dto.request.EmergencyFundRequest;
import com.finset.key_fin.budget.dto.response.BudgetConfirmResponse;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse;
import com.finset.key_fin.budget.dto.response.EmergencyFundResponse;
import com.finset.key_fin.budget.dto.response.BudgetProposalResponse;
import com.finset.key_fin.budget.service.BudgetService;
import com.finset.key_fin.global.base.BaseResponse;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/v1/budgets")
@RequiredArgsConstructor
public class BudgetController implements BudgetControllerDocs {

	private final BudgetService budgetService;

	@PostMapping("/proposals")
	@Override
	public BaseResponse<BudgetProposalResponse> propose(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(budgetService.propose(userId));
	}

	@GetMapping("/current")
	@Override
	public BaseResponse<BudgetCurrentResponse> getCurrent(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(budgetService.getCurrent(userId));
	}

	@PutMapping("/{budgetId}/confirm")
	@Override
	public BaseResponse<BudgetConfirmResponse> confirm(
			@AuthenticationPrincipal Long userId,
			@PathVariable Long budgetId,
			@Valid @RequestBody BudgetConfirmRequest request
	) {
		return BaseResponse.ok(budgetService.confirm(userId, budgetId, request));
	}

	@PutMapping("/{budgetId}/emergency")
	@Override
	public BaseResponse<EmergencyFundResponse> updateEmergency(
			@AuthenticationPrincipal Long userId,
			@PathVariable Long budgetId,
			@Valid @RequestBody EmergencyFundRequest request
	) {
		return BaseResponse.ok(budgetService.updateEmergency(userId, budgetId, request));
	}
}
