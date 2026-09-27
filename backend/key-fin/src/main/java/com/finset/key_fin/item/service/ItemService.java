package com.finset.key_fin.item.service;

import com.finset.key_fin.item.dto.response.AvatarEquipmentResponse;
import com.finset.key_fin.item.dto.response.UserItemResponse;
import java.util.List;

public interface ItemService {
	List<UserItemResponse> getItems(long userId, String slotType);
	AvatarEquipmentResponse getEquipment(long userId);
	AvatarEquipmentResponse updateEquipment(long userId, long userItemId, boolean equipped);
}
