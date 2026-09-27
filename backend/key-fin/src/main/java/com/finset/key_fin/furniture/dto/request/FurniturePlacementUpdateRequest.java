package com.finset.key_fin.furniture.dto.request;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotNull;
import tools.jackson.core.JsonParser;
import tools.jackson.core.JsonToken;
import tools.jackson.databind.DeserializationContext;
import tools.jackson.databind.ValueDeserializer;
import tools.jackson.databind.annotation.JsonDeserialize;

import java.math.BigDecimal;

@Schema(description = "가구 배치 변경. 설치 시 면·방향·좌표 필수, 해제 시 placed 외 필드는 생략 또는 null")
public record FurniturePlacementUpdateRequest(
		@NotNull(message = "설치 여부는 필수입니다.")
		@Schema(description = "true: 설치·이동, false: 해제", requiredMode = Schema.RequiredMode.REQUIRED)
		Boolean placed,
		@Schema(description = "설치 면. FLOOR 가구는 FLOOR, WALL 가구는 LEFT_WALL 또는 RIGHT_WALL")
		FurniturePlacementStatus placementStatus,
		@Schema(description = "설치 방향") FurniturePlacementDirection placementDirection,
		@DecimalMin("0") @DecimalMax("327") @Digits(integer = 3, fraction = 3)
		@Schema(description = "327×586 씬 기준 X 좌표, 소수점 최대 3자리", minimum = "0", maximum = "327", example = "165.000")
		BigDecimal positionX,
		@DecimalMin("0") @DecimalMax("586") @Digits(integer = 3, fraction = 3)
		@Schema(description = "327×586 씬 기준 Y 좌표, 소수점 최대 3자리", minimum = "0", maximum = "586", example = "280.000")
		BigDecimal positionY,
		@JsonDeserialize(using = LayerDeserializer.class)
		@Schema(description = "깊이 보정 정수. 음수 허용. 설치 시 생략 또는 null이면 0", example = "0") Integer layer
) {
	@AssertTrue(message = "설치 시 면·방향·좌표가 필요하며, 해제 시 배치 정보를 보낼 수 없습니다.")
	@JsonIgnore
	@Schema(hidden = true)
	public boolean isConsistentPlacement() {
		if (placed == null) return true; // @NotNull에서 처리한다.
		if (placed) {
			return placementStatus != null && placementDirection != null && positionX != null && positionY != null;
		}
		return placementStatus == null && placementDirection == null && positionX == null && positionY == null && layer == null;
	}

	/** 정수로의 자동 변환으로 소수 부분이 유실되지 않도록 JSON 정수 토큰만 받는다. */
	public static class LayerDeserializer extends ValueDeserializer<Integer> {
		@Override
		public Integer deserialize(JsonParser parser, DeserializationContext context) {
			if (!parser.hasToken(JsonToken.VALUE_NUMBER_INT)) {
				return (Integer) context.handleUnexpectedToken(Integer.class, parser);
			}
			return parser.getIntValue();
		}
	}
}
