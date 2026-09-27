package com.finset.key_fin.auth.controller;

import com.finset.key_fin.auth.dto.request.LoginRequest;
import com.finset.key_fin.auth.dto.request.RefreshTokenRequest;
import com.finset.key_fin.auth.dto.request.SignupRequest;
import com.finset.key_fin.auth.dto.response.AccessTokenResponse;
import com.finset.key_fin.auth.dto.response.LoginResponse;
import com.finset.key_fin.auth.dto.response.SignupResponse;
import com.finset.key_fin.global.base.BaseResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@Tag(
		name = "인증",
		description = "회원가입, 로그인 및 토큰 재발급 API입니다. 세 API 모두 Bearer 인증이 필요하지 않습니다."
)
public interface AuthControllerDocs {

	@Operation(
			summary = "회원가입",
			description = "KeyFin 사용자를 생성하고 프로필과 설정 기본행을 초기화합니다. "
					+ "금융망 연결과 기본 아이템 지급은 별도 과정에서 처리합니다. 탈퇴 이력이 있는 이메일은 다시 가입할 수 없습니다."
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "201",
					description = "회원가입 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "회원가입 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"userId\":1}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "입력값 오류 또는 읽을 수 없는 요청 본문",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = {
									@ExampleObject(name = "입력값 오류", value = "{\"success\":false,\"code\":\"COMMON_001\",\"message\":\"입력값이 올바르지 않습니다.\",\"data\":null}"),
									@ExampleObject(name = "요청 본문 오류", value = "{\"success\":false,\"code\":\"COMMON_002\",\"message\":\"요청 본문을 읽을 수 없습니다.\",\"data\":null}")
							}
					)
			),
			@ApiResponse(
					responseCode = "409",
					description = "이미 가입했거나 탈퇴 이력이 있는 이메일",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = {
									@ExampleObject(name = "이메일 중복", value = "{\"success\":false,\"code\":\"USER_002\",\"message\":\"이미 사용 중인 이메일입니다.\",\"data\":null}"),
									@ExampleObject(name = "탈퇴 이메일", value = "{\"success\":false,\"code\":\"USER_003\",\"message\":\"탈퇴한 이메일은 다시 가입할 수 없습니다.\",\"data\":null}")
							}
					)
			),
			@ApiResponse(responseCode = "405", description = "지원하지 않는 HTTP 메서드", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "415", description = "지원하지 않는 미디어 타입", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류", content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<SignupResponse> signup(
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "가입 이메일, 비밀번호 및 사용자 이름",
					required = true
			)
			SignupRequest request
	);

	@Operation(
			summary = "로그인",
			description = "이메일과 비밀번호를 검증하고 Access Token(30분)과 Refresh Token(14일)을 발급합니다. "
					+ "탈퇴 계정, 존재하지 않는 계정 및 비밀번호 불일치는 같은 오류로 응답합니다."
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "로그인 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "로그인 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"accessToken\":\"eyJhbGciOiJIUzI1NiJ9...\",\"refreshToken\":\"eyJhbGciOiJIUzI1NiJ9...\",\"user\":{\"id\":1,\"name\":\"김예린\"}}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "입력값 오류 또는 읽을 수 없는 요청 본문",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = {
									@ExampleObject(name = "입력값 오류", value = "{\"success\":false,\"code\":\"COMMON_001\",\"message\":\"입력값이 올바르지 않습니다.\",\"data\":null}"),
									@ExampleObject(name = "요청 본문 오류", value = "{\"success\":false,\"code\":\"COMMON_002\",\"message\":\"요청 본문을 읽을 수 없습니다.\",\"data\":null}")
							}
					)
			),
			@ApiResponse(
					responseCode = "401",
					description = "로그인 실패",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(value = "{\"success\":false,\"code\":\"AUTH_001\",\"message\":\"이메일 또는 비밀번호가 올바르지 않습니다.\",\"data\":null}")
					)
			),
			@ApiResponse(responseCode = "405", description = "지원하지 않는 HTTP 메서드", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "415", description = "지원하지 않는 미디어 타입", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류", content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<LoginResponse> login(
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "로그인 이메일과 비밀번호",
					required = true
			)
			LoginRequest request
	);

	@Operation(
			summary = "Access Token 재발급",
			description = "Refresh Token의 서명·만료와 Redis 저장값을 검증하고 새 Access Token(30분)을 발급합니다. "
					+ "기존 Refresh Token은 만료 전까지 유지됩니다."
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "Access Token 재발급 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "재발급 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"accessToken\":\"eyJhbGciOiJIUzI1NiJ9...\"}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "입력값 오류 또는 읽을 수 없는 요청 본문",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = {
									@ExampleObject(name = "입력값 오류", value = "{\"success\":false,\"code\":\"COMMON_001\",\"message\":\"입력값이 올바르지 않습니다.\",\"data\":null}"),
									@ExampleObject(name = "요청 본문 오류", value = "{\"success\":false,\"code\":\"COMMON_002\",\"message\":\"요청 본문을 읽을 수 없습니다.\",\"data\":null}")
							}
					)
			),
			@ApiResponse(
					responseCode = "401",
					description = "유효하지 않거나 만료되었거나 Redis 저장값과 일치하지 않는 Refresh Token",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(value = "{\"success\":false,\"code\":\"AUTH_004\",\"message\":\"유효하지 않은 리프레시 토큰입니다.\",\"data\":null}")
					)
			),
			@ApiResponse(responseCode = "405", description = "지원하지 않는 HTTP 메서드", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "415", description = "지원하지 않는 미디어 타입", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류", content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<AccessTokenResponse> refresh(
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "로그인에서 발급받은 Refresh Token",
					required = true
			)
			RefreshTokenRequest request
	);

	@Operation(
			summary = "로그아웃",
			description = "인증된 사용자의 Redis Refresh Token을 삭제하여 추가 토큰 재발급을 차단합니다. "
					+ "이미 발급된 Access Token은 남은 유효시간 동안 사용할 수 있습니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "로그아웃 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "로그아웃 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":null}"
							)
					)
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(value = "{\"success\":false,\"code\":\"AUTH_002\",\"message\":\"유효하지 않은 토큰입니다.\",\"data\":null}")
					)
			),
			@ApiResponse(responseCode = "405", description = "지원하지 않는 HTTP 메서드", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류", content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<Void> logout(Long userId);
}
