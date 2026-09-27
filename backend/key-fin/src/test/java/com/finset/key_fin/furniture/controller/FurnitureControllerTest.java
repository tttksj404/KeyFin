package com.finset.key_fin.furniture.controller;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;
import com.finset.key_fin.furniture.service.FurnitureService;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.stream.Stream;

import static com.finset.key_fin.furniture.FurnitureFixtures.*;
import static com.finset.key_fin.item.entity.ItemSlotType.FLOOR;
import static org.mockito.Mockito.*;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class FurnitureControllerTest {
	private final FurnitureService service = mock(FurnitureService.class);
	private MockMvc mvc;

	@BeforeEach
	void setUp() {
		mvc = standaloneSetup(new FurnitureController(service)).setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver()).build();
		SecurityContextHolder.getContext().setAuthentication(
				UsernamePasswordAuthenticationToken.authenticated(1L, null, List.of()));
	}

	@AfterEach
	void cleanup() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void listsUsingPrincipalAndOptionalSlotQuery() throws Exception {
		when(service.getFurnitures(1L, null)).thenReturn(List.of());
		mvc.perform(get("/api/v1/furnitures").param("userId", "2"))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data").isEmpty());
		when(service.getFurnitures(1L, "FLOOR")).thenReturn(List.of(UserFurnitureResponse.from(owned(3, FLOOR))));
		mvc.perform(get("/api/v1/furnitures").param("slotType", "FLOOR"))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data[0].userFurnitureId").value(3))
				.andExpect(jsonPath("$.data[0].placed").value(false))
				.andExpect(jsonPath("$.data[0].placementStatus").value(org.hamcrest.Matchers.nullValue()));
		verify(service).getFurnitures(1L, null);
		verify(service).getFurnitures(1L, "FLOOR");
	}

	@ParameterizedTest
	@MethodSource("validBodies")
	void acceptsValidPlacementAndRemoval(String body) throws Exception {
		when(service.updatePlacement(eq(1L), eq(3L), any())).thenAnswer(invocation -> {
			FurniturePlacementUpdateRequest request = invocation.getArgument(2);
			var target = owned(3, FLOOR);
			if (request.placed()) target.place(request.placementStatus(), request.placementDirection(),
					request.positionX(), request.positionY(), request.layer() == null ? 0 : request.layer());
			return UserFurnitureResponse.from(target);
		});
		mvc.perform(patch("/api/v1/furnitures/3").contentType(APPLICATION_JSON).content(body))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.userFurnitureId").value(3))
				.andExpect(jsonPath("$.success").value(true));
		verify(service).updatePlacement(eq(1L), eq(3L), any());
	}

	static Stream<String> validBodies() {
		return Stream.of(PLACEMENT_JSON, PLACEMENT_JSON.replace(",\"layer\":-2", ""),
				PLACEMENT_JSON.replace("\"layer\":-2", "\"layer\":null"),
				PLACEMENT_JSON.replace("165.123", "0").replace("280.456", "404.000"),
				PLACEMENT_JSON.replace("280.456", "404.001"),
				PLACEMENT_JSON.replace("280.456", "586.000"),
				PLACEMENT_JSON.replace("165.123", "327.000").replace("280.456", "0"),
				"{\"placed\":false}",
				"{\"placed\":false,\"placementStatus\":null,\"placementDirection\":null,\"positionX\":null,\"positionY\":null,\"layer\":null}");
	}

	@ParameterizedTest
	@ValueSource(strings = {"0", "-1", "text", "9223372036854775808"})
	void rejectsInvalidIds(String id) throws Exception {
		mvc.perform(patch("/api/v1/furnitures/" + id).contentType(APPLICATION_JSON).content(PLACEMENT_JSON))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_001"));
		verifyNoInteractions(service);
	}

	@ParameterizedTest
	@MethodSource("invalidBodies")
	void rejectsInconsistentStateAndInvalidCoordinatesBeforeCallingService(String body) throws Exception {
		mvc.perform(patch("/api/v1/furnitures/3").contentType(APPLICATION_JSON).content(body))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_001"));
		verifyNoInteractions(service);
	}

	static Stream<String> invalidBodies() {
		return Stream.of("{}", "{\"placed\":null}", "{\"placed\":true}",
				PLACEMENT_JSON.replace("\"placementStatus\":\"FLOOR\",", ""),
				PLACEMENT_JSON.replace("\"placementDirection\":\"FRONT_RIGHT\",", ""),
				PLACEMENT_JSON.replace("\"positionX\":165.123,", ""),
				PLACEMENT_JSON.replace("\"positionY\":280.456,", ""),
				PLACEMENT_JSON.replace("\"FLOOR\"", "null"), PLACEMENT_JSON.replace("\"FRONT_RIGHT\"", "null"),
				PLACEMENT_JSON.replace("165.123", "null"), PLACEMENT_JSON.replace("280.456", "null"),
				PLACEMENT_JSON.replace("165.123", "-0.001"), PLACEMENT_JSON.replace("165.123", "327.001"),
				PLACEMENT_JSON.replace("280.456", "-0.001"), PLACEMENT_JSON.replace("280.456", "586.001"),
				PLACEMENT_JSON.replace("165.123", "1.1234"), PLACEMENT_JSON.replace("280.456", "1.1234"),
				"{\"placed\":false,\"placementStatus\":\"FLOOR\"}",
				"{\"placed\":false,\"placementDirection\":\"FRONT_LEFT\"}",
				"{\"placed\":false,\"positionX\":0}", "{\"placed\":false,\"positionY\":0}",
				"{\"placed\":false,\"layer\":0}");
	}

	@ParameterizedTest
	@MethodSource("unreadableBodies")
	void rejectsUnreadableBodies(String body) throws Exception {
		mvc.perform(patch("/api/v1/furnitures/3").contentType(APPLICATION_JSON).content(body))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_002"));
		verifyNoInteractions(service);
	}

	static Stream<String> unreadableBodies() {
		return Stream.of("", "{", "null", "{\"placed\":[]}",
				PLACEMENT_JSON.replace("\"FLOOR\"", "\"UNKNOWN\""),
				PLACEMENT_JSON.replace("\"FRONT_RIGHT\"", "\"BACK\""),
				PLACEMENT_JSON.replace("\"FLOOR\"", "0"),
				PLACEMENT_JSON.replace("\"FRONT_RIGHT\"", "1"),
				PLACEMENT_JSON.replace("\"layer\":-2", "\"layer\":1.5"),
				PLACEMENT_JSON.replace("\"layer\":-2", "\"layer\":2147483648"));
	}
}
