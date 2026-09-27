package com.finset.key_fin.notification.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record PushDeviceRequest(
		@NotBlank @Size(max = 2048) @Pattern(regexp = "[\\x21-\\x7E]+") String token,
		@NotBlank @Pattern(regexp = "ANDROID") String platform
) {
	@Override
	public String toString() {
		return "PushDeviceRequest[token=******, platform=" + platform + "]";
	}
}
