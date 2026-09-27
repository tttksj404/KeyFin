package com.finset.key_fin.coaching.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChatRequest(
		@NotBlank @Size(max = 2000) String message
) {
}
