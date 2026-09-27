package com.finset.key_fin.transaction.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "봉투별 세분류 목록")
public record SubcategoryListResponse(
		@Schema(description = "봉투 목록")
		List<EnvelopeItem> items
) {

	public record EnvelopeItem(
			@Schema(description = "봉투 ID", example = "1")
			Integer envelopeId,
			@Schema(description = "봉투명", example = "외식")
			String envelopeName,
			@Schema(description = "세분류 목록")
			List<SubcategoryItem> subcategories
	) {
	}

	public record SubcategoryItem(
			@Schema(description = "세분류 ID", example = "102")
			Integer id,
			@Schema(description = "세분류명", example = "카페")
			String name
	) {
	}
}
