package com.finset.key_fin.shop.service;

import com.finset.key_fin.shop.dto.response.ShopItemResponse;
import com.finset.key_fin.shop.dto.response.ShopPurchaseResponse;

import java.util.List;

public interface ShopService {
	List<ShopItemResponse> getItems(long userId, String itemCategory, String slotType);

	ShopPurchaseResponse purchase(long userId, long itemId);
}
