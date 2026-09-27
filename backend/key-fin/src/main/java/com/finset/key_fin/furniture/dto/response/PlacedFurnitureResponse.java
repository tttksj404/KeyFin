package com.finset.key_fin.furniture.dto.response;

import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.furniture.entity.DefaultFurnitureType;
import com.finset.key_fin.furniture.entity.FurnitureType;
import com.finset.key_fin.item.entity.ItemSlotType;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "방에 설치된 가구")
public record PlacedFurnitureResponse(
		@Schema(requiredMode = REQUIRED) Long userFurnitureId,
		@Schema(requiredMode = REQUIRED) Long itemId,
		@Schema(requiredMode = REQUIRED, allowableValues = {"FLOOR", "WALL"}) ItemSlotType slotType,
		@Schema(requiredMode = REQUIRED) String assetKey,
		@Schema(requiredMode = REQUIRED) FurniturePlacementStatus placementStatus,
		@Schema(requiredMode = REQUIRED) FurniturePlacementDirection placementDirection,
		@Schema(requiredMode = REQUIRED) BigDecimal positionX,
		@Schema(requiredMode = REQUIRED) BigDecimal positionY,
		@Schema(requiredMode = REQUIRED) int layer,
		@Schema(requiredMode = REQUIRED, nullable = true) DefaultFurnitureType defaultFurnitureType,
		@Schema(description = "색상과 무관한 필수 가구 종류. 그 외 가구는 null", requiredMode = REQUIRED, nullable = true) FurnitureType furnitureType,
		@Schema(requiredMode = REQUIRED) boolean stickerAttached,
		@Schema(description = "단독 해제 가능 여부. 설치된 필수 가구는 일괄 저장으로만 교체 가능", requiredMode = REQUIRED) boolean canUnplace
) {
	public static PlacedFurnitureResponse from(UserFurniture furniture) {
		var item = furniture.getItem();
		return new PlacedFurnitureResponse(furniture.getId(), item.getId(), item.getSlotType(), item.getAssetKey(),
				furniture.getPlacementStatus(), furniture.getPlacementDirection(),
				furniture.getPositionX(), furniture.getPositionY(), furniture.getLayer(),
				item.getDefaultFurnitureType(), item.getFurnitureType(), furniture.isStickerAttached(), furniture.canUnplace());
	}
}
