package com.finset.key_fin.room.controller;

import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.room.dto.response.RoomResponse;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.dto.response.PlacedFurnitureResponse;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.dto.response.EquippedItemResponse;
import com.finset.key_fin.room.service.RoomService;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.room.dto.response.StickerStatusResponse;
import com.finset.key_fin.furniture.entity.DefaultFurnitureType;
import com.finset.key_fin.furniture.entity.FurnitureType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class RoomControllerTest {

	private RoomService roomService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		roomService = mock(RoomService.class);
		mockMvc = standaloneSetup(new RoomController(roomService, mock(RoomStickerService.class)))
				.setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
				.build();
	}

	@Test
	void returnsRoomHomeDataForAuthenticatedUser() throws Exception {
		RoomResponse response = roomResponse();
		when(roomService.getRoom(1L)).thenReturn(response);
		UsernamePasswordAuthenticationToken authentication =
				UsernamePasswordAuthenticationToken.authenticated(1L, null, List.of());
		SecurityContextHolder.getContext().setAuthentication(authentication);

		try {
			mockMvc.perform(get("/api/v1/room"))
					.andExpect(status().isOk())
					.andExpect(jsonPath("$.success").value(true))
					.andExpect(jsonPath("$.code").value("SUCCESS"))
					.andExpect(jsonPath("$.data.theme").doesNotHaveJsonPath())
					.andExpect(jsonPath("$.data.avatar.equipped[0].slotType").value("HEAD"))
					.andExpect(jsonPath("$.data.avatar.equipped[0].itemId").value(1))
					.andExpect(jsonPath("$.data.avatar.equipped[0].userItemId").value(101))
					.andExpect(jsonPath("$.data.avatar.reaction").doesNotExist())
					.andExpect(jsonPath("$.data.furnitures[0].itemId").value(4))
					.andExpect(jsonPath("$.data.furnitures[0].userFurnitureId").value(201))
					.andExpect(jsonPath("$.data.furnitures[0].placementStatus").value("FLOOR"))
					.andExpect(jsonPath("$.data.furnitures[0].placementDirection").value("FRONT_RIGHT"))
					.andExpect(jsonPath("$.data.furnitures[0].positionX").value(165.000))
					.andExpect(jsonPath("$.data.coin.balance").value(1250))
					.andExpect(jsonPath("$.data.board").doesNotHaveJsonPath())
					.andExpect(jsonPath("$.data.overEnvelopes[0]").value(1))
					.andExpect(jsonPath("$.data.overEnvelopes[1]").value(4))
					.andExpect(jsonPath("$.data.attendance.checkedToday").value(false));

			verify(roomService).getRoom(1L);
		} finally {
			SecurityContextHolder.clearContext();
		}
	}

	private RoomResponse roomResponse() {
		return new RoomResponse(
				new RoomResponse.AvatarResponse(
						List.of(
								new EquippedItemResponse(101L, 1L, ItemSlotType.HEAD, "hat_blue"),
								new EquippedItemResponse(102L, 2L, ItemSlotType.FACE, "glasses_round"),
								new EquippedItemResponse(103L, 3L, ItemSlotType.UPPER_BODY, "shirt_blue")
						),
						null
				),
				List.of(
						new PlacedFurnitureResponse(
								201L,
								4L,
								ItemSlotType.FLOOR,
								"sofa_default",
								FurniturePlacementStatus.FLOOR,
								FurniturePlacementDirection.FRONT_RIGHT,
								new BigDecimal("165.000"),
								new BigDecimal("280.000"),
								0, DefaultFurnitureType.SOFA, FurnitureType.SOFA, false, false
						)
				),
				new RoomResponse.CoinResponse(1250),
				new RoomResponse.AttendanceResponse(false),
				new StickerStatusResponse(0, 3, false),
				List.of(1, 4)
		);
	}
}
