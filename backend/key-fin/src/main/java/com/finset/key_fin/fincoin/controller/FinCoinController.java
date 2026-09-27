package com.finset.key_fin.fincoin.controller;

import com.finset.key_fin.fincoin.dto.response.AttendanceCheckResponse;
import com.finset.key_fin.fincoin.dto.response.FinCoinBalanceResponse;
import com.finset.key_fin.fincoin.dto.response.FinCoinResponse;
import com.finset.key_fin.fincoin.service.FinCoinService;
import com.finset.key_fin.global.base.BaseResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/fin-coins")
@RequiredArgsConstructor
public class FinCoinController implements FinCoinControllerDocs {

	private final FinCoinService finCoinService;

	@GetMapping(produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<FinCoinResponse> getFinCoins(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) Long cursor,
			@RequestParam(defaultValue = "20") Integer size
	) {
		return BaseResponse.ok(finCoinService.getFinCoins(userId, cursor, size));
	}

	@GetMapping(value = "/balance", produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<FinCoinBalanceResponse> getFinCoinBalance(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(finCoinService.getFinCoinBalance(userId));
	}

	@PostMapping(value = "/attendance", produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<AttendanceCheckResponse> checkAttendance(@AuthenticationPrincipal Long userId) {
		return BaseResponse.ok(finCoinService.checkAttendance(userId));
	}
}
