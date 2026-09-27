package com.finset.key_fin.user.controller;

import com.finset.key_fin.user.dto.request.AccountDeletionRequest;
import com.finset.key_fin.user.service.UserService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController implements UserControllerDocs {

	private final UserService userService;

	@DeleteMapping("/me")
	@Override
	public ResponseEntity<Void> deleteAccount(
			@AuthenticationPrincipal Long userId,
			@Valid @RequestBody AccountDeletionRequest request
	) {
		userService.deleteAccount(userId, request);
		return ResponseEntity.noContent().build();
	}
}
