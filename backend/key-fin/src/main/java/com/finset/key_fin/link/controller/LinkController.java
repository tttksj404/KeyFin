package com.finset.key_fin.link.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.link.dto.request.FinanceConnectRequest;
import com.finset.key_fin.link.dto.request.LinkAssetsRequest;
import com.finset.key_fin.link.dto.response.FinanceConnectResponse;
import com.finset.key_fin.link.dto.response.LinkAssetsResponse;
import com.finset.key_fin.link.dto.response.LinkCandidatesResponse;
import com.finset.key_fin.link.service.FinanceConnectService;
import com.finset.key_fin.link.service.AssetLinkService;
import com.finset.key_fin.link.service.LinkCandidateService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.http.HttpStatus.CREATED;

@RestController
@RequestMapping("/api/v1/links")
@RequiredArgsConstructor
public class LinkController implements LinkControllerDocs {

	private final FinanceConnectService financeConnectService;
	private final LinkCandidateService linkCandidateService;
	private final AssetLinkService assetLinkService;

	@PostMapping("/connect")
	@Override
	public BaseResponse<FinanceConnectResponse> connect(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody FinanceConnectRequest request
	) {
		return BaseResponse.ok(financeConnectService.connect(userId, request));
	}

	@GetMapping("/status")
	@Override
	public BaseResponse<FinanceConnectResponse> getStatus(
			@AuthenticationPrincipal Long userId
	) {
		return BaseResponse.ok(financeConnectService.getStatus(userId));
	}

	@GetMapping("/candidates")
	@Override
	public BaseResponse<LinkCandidatesResponse> getCandidates(
			@AuthenticationPrincipal Long userId
	) {
		return BaseResponse.ok(linkCandidateService.getCandidates(userId));
	}

	@PostMapping
	@ResponseStatus(CREATED)
	@Override
	public BaseResponse<LinkAssetsResponse> link(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody LinkAssetsRequest request
	) {
		return BaseResponse.ok(assetLinkService.link(userId, request));
	}

	@DeleteMapping("/accounts/{accountId}")
	@Override
	public BaseResponse<Void> unlinkAccount(
			@AuthenticationPrincipal Long userId,
			@PathVariable long accountId
	) {
		assetLinkService.unlinkAccount(userId, accountId);
		return BaseResponse.ok();
	}

	@DeleteMapping("/cards/{cardId}")
	@Override
	public BaseResponse<Void> unlinkCard(
			@AuthenticationPrincipal Long userId,
			@PathVariable long cardId
	) {
		assetLinkService.unlinkCard(userId, cardId);
		return BaseResponse.ok();
	}
}
