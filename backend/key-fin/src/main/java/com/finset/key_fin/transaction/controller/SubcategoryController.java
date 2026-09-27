package com.finset.key_fin.transaction.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.transaction.dto.response.SubcategoryListResponse;
import com.finset.key_fin.transaction.service.SubcategoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@RestController
@RequestMapping("/api/v1/subcategories")
@RequiredArgsConstructor
public class SubcategoryController implements SubcategoryControllerDocs {

	private final SubcategoryService subcategoryService;

	@GetMapping(produces = APPLICATION_JSON_VALUE)
	@Override
	public BaseResponse<SubcategoryListResponse> getSubcategories(
			@AuthenticationPrincipal Long userId
	) {
		return BaseResponse.ok(subcategoryService.getSubcategories(userId));
	}
}
