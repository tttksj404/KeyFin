package com.finset.key_fin.room.dto.response;

public record StickerRemovalResponse(long userFurnitureId, boolean stickerAttached, StickerStatusResponse stickers) {
}
