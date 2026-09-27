package com.finset.key_fin.account.controller;

import com.finset.key_fin.account.dto.response.AccountListResponse;
import com.finset.key_fin.account.service.AccountService;
import com.finset.key_fin.global.base.BaseResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/accounts")
@RequiredArgsConstructor
public class AccountController implements AccountControllerDocs {

	private final AccountService accountService;

	@GetMapping(produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<AccountListResponse> getAccounts(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(accountService.getManagedAccounts(userId));
	}

	@PutMapping(value = "/{id}/income", produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<Void> designateIncomeAccount(
			@AuthenticationPrincipal Long userId,
			@PathVariable long id
	) {
		accountService.designateIncomeAccount(userId, id);
		return BaseResponse.ok();
	}
}
