package com.finset.key_fin.furniture.controller;

import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class FurnitureDocumentationIntegrationTest extends SpringIntegrationTestSupport {
	@Autowired private MockMvc mvc;

	@Test
	void documentsFurnitureApiAndSharedRoomPlacementSchema() throws Exception {
		mvc.perform(get("/v3/api-docs")).andExpect(status().isOk())
				.andExpect(jsonPath("$.paths['/api/v1/furnitures'].get.parameters[*].name", contains("slotType")))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures'].get.parameters[0].required").value(false))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures'].get.parameters[0].schema.enum", containsInAnyOrder("FLOOR", "WALL")))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures'].get.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/{userFurnitureId}'].patch.parameters[*].name", contains("userFurnitureId")))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/{userFurnitureId}'].patch.requestBody.required").value(true))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/{userFurnitureId}'].patch.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/{userFurnitureId}'].patch.responses['200'].content['application/json'].schema['$ref']")
						.value("#/components/schemas/BaseResponseUserFurnitureResponse"))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/{userFurnitureId}'].patch.responses['400']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/{userFurnitureId}'].patch.responses['404']").exists())
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementUpdateRequest.required", contains("placed")))
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementUpdateRequest.properties", aMapWithSize(6)))
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementUpdateRequest.properties.placed.type").value("boolean"))
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementUpdateRequest.properties.layer.type").value("integer"))
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementUpdateRequest.properties.positionX.maximum").value(327))
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementUpdateRequest.properties.positionY.maximum").value(586))
				.andExpect(jsonPath("$.components.schemas.UserFurnitureResponse.properties", aMapWithSize(15)))
				.andExpect(jsonPath("$.components.schemas.UserFurnitureResponse.required", containsInAnyOrder(
						"userFurnitureId", "itemId", "name", "slotType", "assetKey", "placed", "placementStatus", "placementDirection", "positionX", "positionY", "layer",
						"defaultFurnitureType", "furnitureType", "stickerAttached", "canUnplace")))
				.andExpect(jsonPath("$.components.schemas.PlacedFurnitureResponse.properties", aMapWithSize(13)))
				.andExpect(jsonPath("$.components.schemas.PlacedFurnitureResponse.properties.furnitureType.enum", containsInAnyOrder("SOFA", "TV", "DINING_TABLE", "COFFEE_TABLE")))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/placements'].put.requestBody.required").value(true))
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/placements'].put.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/placements'].put.responses['409']").exists())
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementsUpdateRequest.properties.placements.maxItems").value(100))
				.andExpect(jsonPath("$.components.schemas.FurniturePlacementEntry.properties.positionY.maximum").value(586))
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.furnitures.items['$ref']")
						.value("#/components/schemas/PlacedFurnitureResponse"));
	}
}
