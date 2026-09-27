import * as React from "react";
import { Pressable } from "react-native";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { Text } from "@/components/ui/text";
import { useRemoveSticker } from "@/features/room/api/queries";
import { roomItemName } from "@/features/room/catalog";
import { getSceneScale, sortByDepth, type PlacedFurnitureDto, type RoomStickers } from "@/features/room/model";
import { placementView, type Placement } from "@/features/room/scene";
import { stickerErrorMessage, stickerGeometry, stickerPlacements } from "@/features/room/stickers";

type TargetsProps = {
  width: number;
  placements: readonly Placement[];
  furnitures: readonly PlacedFurnitureDto[];
  onSelect: (placement: Placement) => void;
};

/** 그림은 Skia가 그리고, 이 버튼들은 RoomView의 같은 카메라 변환 안에서 움직인다. */
export function RoomStickerTargets({ width, placements, furnitures, onSelect }: TargetsProps) {
  const scale = getSceneScale(width);
  const stamped = stickerPlacements(placements, furnitures);
  const sorted = [...stamped.filter((p) => placementView(p).flat), ...sortByDepth(stamped.filter((p) => !placementView(p).flat))];
  return <>{sorted.map((placement) => {
    const geometry = stickerGeometry(placement);
    if (!geometry) return null;
    const { rect, angle } = geometry;
    return <Pressable key={placement.userFurnitureId} accessibilityRole="button"
      accessibilityLabel={`${roomItemName(placement.itemId)} 압류 딱지`}
      accessibilityHint="압류 딱지 제거 안내를 엽니다" onPress={() => onSelect(placement)}
      hitSlop={6} style={{ position: "absolute", left: rect.x * scale, top: rect.y * scale,
        width: rect.width * scale, height: rect.height * scale, transform: [{ rotate: `${angle}rad` }] }} />;
  })}</>;
}

export function StickerRemovalDialog({ placement, stickers, onClose }: {
  placement: Placement;
  stickers: RoomStickers | null;
  onClose: () => void;
}) {
  const removal = useRemoveSticker();
  const pending = React.useRef(false);
  const [error, setError] = React.useState<string | null>(null);
  const remove = async () => {
    if (pending.current || !stickers?.removableToday || placement.userFurnitureId === undefined) return;
    pending.current = true;
    setError(null);
    try {
      await removal.mutateAsync(placement.userFurnitureId);
      onClose();
    } catch (cause) {
      setError(stickerErrorMessage(cause));
    } finally {
      pending.current = false;
    }
  };
  return <Dialog open onOpenChange={(open) => { if (!open && !pending.current) onClose(); }}>
    <DialogContent>
      <DialogTitle>압류 딱지 제거</DialogTitle>
      <DialogDescription>{`${roomItemName(placement.itemId)}에 붙은 압류 딱지를 제거할까요?`}</DialogDescription>
      <Text className="text-body text-foreground">{`설치된 바닥 가구 ${stickers?.total ?? 0}개 중 딱지 ${stickers?.count ?? 0}개`}</Text>
      {stickers?.count === 0 ? <Text className="text-caption text-card-foreground">설치된 가구에 남은 딱지가 없어요.</Text> : null}
      {error ? <Text accessibilityRole="alert" className="text-caption text-destructive">{error}</Text> : null}
      <DialogFooter>
        <Button variant="secondary" onPress={onClose} disabled={removal.isPending}><Text>닫기</Text></Button>
        <Button onPress={() => { void remove(); }} disabled={removal.isPending || !stickers?.removableToday}>
          <Text>{removal.isPending ? "제거 중…" : "딱지 제거"}</Text>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}
