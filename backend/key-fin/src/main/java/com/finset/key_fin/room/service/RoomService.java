package com.finset.key_fin.room.service;

import com.finset.key_fin.room.dto.response.RoomResponse;

public interface RoomService {

	RoomResponse getRoom(long userId);
}
