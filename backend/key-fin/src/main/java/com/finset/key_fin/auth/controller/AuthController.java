package com.finset.key_fin.auth.controller;

import com.finset.key_fin.auth.dto.request.LoginRequest;
import com.finset.key_fin.auth.dto.request.RefreshTokenRequest;
import com.finset.key_fin.auth.dto.request.SignupRequest;
import com.finset.key_fin.auth.dto.response.AccessTokenResponse;
import com.finset.key_fin.auth.dto.response.LoginResponse;
import com.finset.key_fin.auth.dto.response.SignupResponse;
import com.finset.key_fin.auth.service.AuthService;
import com.finset.key_fin.global.base.BaseResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.http.HttpStatus.CREATED;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController implements AuthControllerDocs {

	private final AuthService authService;

	@PostMapping("/signup")
	@ResponseStatus(CREATED)
	@Override
	public BaseResponse<SignupResponse> signup(@Valid @RequestBody SignupRequest request) {
		return BaseResponse.ok(authService.signup(request));
	}

	@PostMapping("/login")
	@Override
	public BaseResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
		return BaseResponse.ok(authService.login(request));
	}

	@PostMapping("/refresh")
	@Override
	public BaseResponse<AccessTokenResponse> refresh(
			@Valid @RequestBody RefreshTokenRequest request
	) {
		return BaseResponse.ok(authService.refresh(request));
	}

	@PostMapping("/logout")
	@Override
	public BaseResponse<Void> logout(@AuthenticationPrincipal Long userId) {
		authService.logout(userId);
		return BaseResponse.ok();
	}
}
