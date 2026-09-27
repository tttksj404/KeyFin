package com.finset.key_fin.user.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.user.dto.request.ProfileUpdateRequest;
import com.finset.key_fin.user.dto.response.ProfileResponse;
import com.finset.key_fin.user.service.ProfileService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/profile")
@RequiredArgsConstructor
public class ProfileController implements ProfileControllerDocs {

	private final ProfileService profileService;

	@PutMapping(consumes = APPLICATION_JSON_VALUE, produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<ProfileResponse> updateProfile(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody ProfileUpdateRequest request
	) {
		return BaseResponse.ok(profileService.updateProfile(userId, request));
	}
}
