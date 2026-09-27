package com.finset.key_fin.global.exception;

import com.finset.key_fin.global.base.BaseResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.ErrorResponseException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class GlobalExceptionHandlerTest {

	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		mockMvc = standaloneSetup(new TestController())
				.setControllerAdvice(new GlobalExceptionHandler())
				.build();
	}

	@Test
	void serializesSuccessWithData() throws Exception {
		mockMvc.perform(get("/test/success"))
				.andExpect(status().isOk())
				.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.code").value("SUCCESS"))
				.andExpect(jsonPath("$.message").value("요청이 성공했습니다."))
				.andExpect(jsonPath("$.data.id").value(1));
	}

	@Test
	void serializesSuccessWithoutDataAsExplicitNull() throws Exception {
		mockMvc.perform(get("/test/empty"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.code").value("SUCCESS"))
				.andExpect(jsonPath("$.message").value("요청이 성공했습니다."))
				.andExpect(jsonPath("$.data").hasJsonPath())
				.andExpect(jsonPath("$.data").value(nullValue()));
	}

	@Test
	void preservesBusinessErrorAndHidesCause() throws Exception {
		mockMvc.perform(get("/test/business"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("USER_NOT_FOUND"))
				.andExpect(jsonPath("$.message").value("사용자를 찾을 수 없습니다."))
				.andExpect(jsonPath("$.data").hasJsonPath())
				.andExpect(jsonPath("$.data").value(nullValue()))
				.andExpect(content().string(not(containsString("internal database detail"))));
	}

	@Test
	void rejectsInvalidRequestBody() throws Exception {
		mockMvc.perform(post("/test/validated")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"name\":\"\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_001"))
				.andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."));
	}

	@Test
	void rejectsInvalidMethodParameter() throws Exception {
		mockMvc.perform(get("/test/parameter").param("count", "0"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@Test
	void rejectsMalformedJsonWithoutExposingParserDetails() throws Exception {
		mockMvc.perform(post("/test/validated")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"name\":"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_002"))
				.andExpect(jsonPath("$.message").value("요청 본문을 읽을 수 없습니다."));
	}

	@Test
	void preservesMethodNotAllowedStatusAndAllowHeader() throws Exception {
		mockMvc.perform(post("/test/success"))
				.andExpect(status().isMethodNotAllowed())
				.andExpect(header().string(HttpHeaders.ALLOW, containsString("GET")))
				.andExpect(jsonPath("$.code").value("COMMON_003"))
				.andExpect(jsonPath("$.message").value("지원하지 않는 HTTP 메서드입니다."));
	}

	@Test
	void preservesUnsupportedMediaTypeStatus() throws Exception {
		mockMvc.perform(post("/test/validated")
						.contentType(MediaType.TEXT_PLAIN)
						.content("name"))
				.andExpect(status().isUnsupportedMediaType())
				.andExpect(jsonPath("$.code").value("COMMON_004"));
	}

	@ParameterizedTest
	@CsvSource({
			"401, COMMON_005, 요청을 처리할 수 없습니다.",
			"403, COMMON_005, 요청을 처리할 수 없습니다.",
			"404, COMMON_005, 요청을 처리할 수 없습니다."
	})
	void mapsMvcClientErrorsWithoutExposingReason(
			int httpStatus, String code, String message
	) throws Exception {
		mockMvc.perform(get("/test/status/{status}", httpStatus))
				.andExpect(status().is(httpStatus))
				.andExpect(jsonPath("$.code").value(code))
				.andExpect(jsonPath("$.message").value(message))
				.andExpect(content().string(not(containsString("internal reason"))));
	}

	@Test
	void preservesMvcServerErrorStatusAndHeaders() throws Exception {
		mockMvc.perform(get("/test/unavailable"))
				.andExpect(status().isServiceUnavailable())
				.andExpect(header().string(HttpHeaders.RETRY_AFTER, "30"))
				.andExpect(jsonPath("$.code").value("COMMON_006"))
				.andExpect(jsonPath("$.message").value("서버 내부 오류가 발생했습니다."));
	}

	@Test
	void hidesUnexpectedExceptionDetails() throws Exception {
		mockMvc.perform(get("/test/unexpected"))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_006"))
				.andExpect(jsonPath("$.message").value("서버 내부 오류가 발생했습니다."))
				.andExpect(jsonPath("$.data").hasJsonPath())
				.andExpect(jsonPath("$.data").value(nullValue()))
				.andExpect(content().string(not(containsString("internal database detail"))));
	}

	@RestController
	static class TestController {

		@GetMapping("/test/success")
		BaseResponse<Map<String, Long>> success() {
			return BaseResponse.ok(Map.of("id", 1L));
		}

		@GetMapping("/test/empty")
		BaseResponse<Void> empty() {
			return BaseResponse.ok();
		}

		@GetMapping("/test/business")
		BaseResponse<Void> business() {
			throw new BusinessException(
					TestErrorCode.USER_NOT_FOUND,
					new IllegalStateException("internal database detail")
			);
		}

		@PostMapping("/test/validated")
		BaseResponse<Void> validated(@Valid @RequestBody TestRequest request) {
			return BaseResponse.ok();
		}

		@GetMapping("/test/parameter")
		BaseResponse<Void> parameter(@RequestParam("count") @Min(1) int count) {
			return BaseResponse.ok();
		}

		@GetMapping("/test/status/{status}")
		BaseResponse<Void> mvcError(@PathVariable("status") int status) {
			throw new ResponseStatusException(HttpStatus.valueOf(status), "internal reason");
		}

		@GetMapping("/test/unavailable")
		BaseResponse<Void> unavailable() {
			ErrorResponseException exception = new ErrorResponseException(HttpStatus.SERVICE_UNAVAILABLE);
			exception.getHeaders().set(HttpHeaders.RETRY_AFTER, "30");
			throw exception;
		}

		@GetMapping("/test/unexpected")
		BaseResponse<Void> unexpected() {
			throw new IllegalStateException("internal database detail");
		}
	}

	record TestRequest(@NotBlank String name) {
	}

	@Getter
	@RequiredArgsConstructor
	private enum TestErrorCode implements ErrorCode {

		USER_NOT_FOUND(HttpStatus.NOT_FOUND, "USER_NOT_FOUND", "사용자를 찾을 수 없습니다.");

		private final HttpStatus httpStatus;
		private final String code;
		private final String message;
	}
}
