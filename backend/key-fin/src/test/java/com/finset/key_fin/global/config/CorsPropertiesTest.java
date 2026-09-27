package com.finset.key_fin.global.config;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;

class CorsPropertiesTest {

	@Test
	void 허용_Origin_목록을_보관한다() {
		CorsProperties properties = new CorsProperties(List.of("http://localhost:[*]", "https://keyfin.example.com"));

		assertThat(properties.allowedOrigins())
				.containsExactly("http://localhost:[*]", "https://keyfin.example.com");
	}

	@Test
	void 허용_Origin이_없으면_생성할_수_없다() {
		assertThatIllegalArgumentException().isThrownBy(() -> new CorsProperties(null));
		assertThatIllegalArgumentException().isThrownBy(() -> new CorsProperties(List.of()));
	}

	@Test
	void 비어_있는_Origin_값은_허용하지_않는다() {
		assertThatIllegalArgumentException().isThrownBy(() -> new CorsProperties(List.of(" ")));
		assertThatIllegalArgumentException()
				.isThrownBy(() -> new CorsProperties(Arrays.asList("http://localhost:[*]", null)));
	}
}
