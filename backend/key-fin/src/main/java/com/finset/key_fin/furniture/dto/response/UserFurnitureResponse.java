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

@Schema(description = "사용자가 보유한 가구와 배치 상태")
public record UserFurnitureResponse(
		@Schema(description = "보유 가구 ID. 배치 변경 요청에 사용", requiredMode = REQUIRED) Long userFurnitureId,
		@Schema(description = "상품 ID", requiredMode = REQUIRED) Long itemId,
		@Schema(requiredMode = REQUIRED) String name,
		@Schema(requiredMode = REQUIRED, allowableValues = {"FLOOR", "WALL"}) ItemSlotType slotType,
		@Schema(requiredMode = REQUIRED) String assetKey,
		@Schema(description = "현재 설치 여부", requiredMode = REQUIRED) boolean placed,
		@Schema(description = "설치 면. 미설치 시 null", requiredMode = REQUIRED, nullable = true) FurniturePlacementStatus placementStatus,
		@Schema(description = "설치 방향. 미설치 시 null", requiredMode = REQUIRED, nullable = true) FurniturePlacementDirection placementDirection,
		@Schema(description = "X 좌표. 미설치 시 null", requiredMode = REQUIRED, nullable = true) BigDecimal positionX,
		@Schema(description = "Y 좌표. 미설치 시 null", requiredMode = REQUIRED, nullable = true) BigDecimal positionY,
		@Schema(description = "깊이 보정값. 미설치 시 0", requiredMode = REQUIRED) int layer,
		@Schema(description = "기본 지급 상품 식별값. 그 외 상품은 null", requiredMode = REQUIRED, nullable = true) DefaultFurnitureType defaultFurnitureType,
		@Schema(description = "색상과 무관한 필수 가구 종류. 그 외 가구는 null", requiredMode = REQUIRED, nullable = true) FurnitureType furnitureType,
		@Schema(requiredMode = REQUIRED) boolean stickerAttached,
		@Schema(description = "단독 해제 가능 여부. 설치된 필수 가구는 false이며 일괄 저장으로 같은 종류와 교체 가능", requiredMode = REQUIRED) boolean canUnplace
) {
	public static UserFurnitureResponse from(UserFurniture furniture) {
		var item = furniture.getItem();
		return new UserFurnitureResponse(furniture.getId(), item.getId(), item.getName(), item.getSlotType(),
				item.getAssetKey(), furniture.isPlaced(), furniture.getPlacementStatus(), furniture.getPlacementDirection(),
				furniture.getPositionX(), furniture.getPositionY(), furniture.getLayer(),
				item.getDefaultFurnitureType(), item.getFurnitureType(), furniture.isStickerAttached(), furniture.canUnplace());
	}
}
