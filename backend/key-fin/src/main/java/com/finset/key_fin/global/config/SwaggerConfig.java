package com.finset.key_fin.global.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

	public static final String BEARER_AUTH = "bearerAuth";

	@Bean
	public OpenAPI keyFinOpenApi() {
		return new OpenAPI()
				.info(new Info()
						.title("KeyFin API")
						.description("계획적인 소비 습관을 위한 KeyFin 백엔드 API 문서")
						.version("v1"))
				.components(new Components()
						.addSecuritySchemes(BEARER_AUTH, new SecurityScheme()
								.name(BEARER_AUTH)
								.type(SecurityScheme.Type.HTTP)
								.scheme("bearer")
								.bearerFormat("JWT")
								.description("로그인에서 발급받은 Access Token을 입력합니다.")));
	}
}
