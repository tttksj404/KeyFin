package com.finset.key_fin.furniture.dto.request;

import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import tools.jackson.databind.annotation.JsonDeserialize;

import java.math.BigDecimal;
import java.util.List;

@Schema(description = "방의 최종 배치 전체. 목록에서 빠진 보유 가구는 보관 상태로 전환")
public record FurniturePlacementsUpdateRequest(
		@NotNull @Size(max = 100)
		@Schema(description = "변경분이 아닌 최종 설치 가구 전체. 소파·TV·식탁·커피테이블 각각 정확히 1개 필수", requiredMode = Schema.RequiredMode.REQUIRED)
		List<@NotNull @Valid Placement> placements
) {
	@Schema(name = "FurniturePlacementEntry", description = "최종 배치의 가구 한 개. 종류와 딱지는 서버가 판단")
	public record Placement(
			@NotNull @Positive Long userFurnitureId,
			@NotNull FurniturePlacementStatus placementStatus,
			@NotNull FurniturePlacementDirection placementDirection,
			@NotNull @DecimalMin("0") @DecimalMax("327") @Digits(integer = 3, fraction = 3)
			@Schema(description = "327×586 씬 기준 X 좌표", minimum = "0", maximum = "327") BigDecimal positionX,
			@NotNull @DecimalMin("0") @DecimalMax("586") @Digits(integer = 3, fraction = 3)
			@Schema(description = "327×586 씬 기준 Y 좌표", minimum = "0", maximum = "586") BigDecimal positionY,
			@JsonDeserialize(using = FurniturePlacementUpdateRequest.LayerDeserializer.class)
			@Schema(description = "깊이 보정 정수. 음수 허용, 생략·null은 0") Integer layer
	) {}
}
