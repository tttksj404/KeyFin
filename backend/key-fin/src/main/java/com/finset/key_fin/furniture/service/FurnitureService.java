package com.finset.key_fin.furniture.service;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest;
import com.finset.key_fin.furniture.dto.response.PlacedFurnitureResponse;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;

import java.util.List;

public interface FurnitureService {
	List<UserFurnitureResponse> getFurnitures(long userId, String slotType);
	List<PlacedFurnitureResponse> getPlacedFurnitures(long userId);
	UserFurnitureResponse updatePlacement(long userId, long userFurnitureId, FurniturePlacementUpdateRequest request);
	List<UserFurnitureResponse> updatePlacements(long userId, FurniturePlacementsUpdateRequest request);
}
