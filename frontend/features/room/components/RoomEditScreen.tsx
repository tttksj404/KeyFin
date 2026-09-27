import { useRouter } from "expo-router";
import { usePreventRemove } from "expo-router/react-navigation";
import { Archive, ChevronUp, CircleAlert, FlipHorizontal2, Sofa } from "lucide-react-native";
import * as React from "react";
import { FlatList, Pressable, View, type LayoutChangeEvent } from "react-native";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { roomItemName, roomItemThumbnail, roomItemThumbnailGeometry, isWallItemId } from "@/features/room/catalog";
import { FurnitureThumbnail } from "@/features/room/components/FurnitureThumbnail";
import { RoomView } from "@/features/room/components/RoomView";
import {
  storeAwayBlock,
  storedFurnitures,
  type StoreAwayBlock,
  type StoredFurniture,
  type UserFurniture,
} from "@/features/room/furniture";
import {
  containSceneWidth,
  getCanvasSize,
  getSceneScale,
  getSpriteRect,
  placeBubble,
  sceneRectToCanvas,
  type SceneSize,
} from "@/features/room/model";
import { placeNewItem, placementView, type Placement } from "@/features/room/scene";
import { selectPlacements, useRoomStore } from "@/features/room/store";
import { useRoomEditor } from "@/features/room/useRoomEditor";
import { cn } from "@/lib/utils";

export const EDIT_TITLE = "방 꾸미기";
export const EDIT_HINT = "가구를 끌어서 옮기세요. 누르면 방향을 바꾸거나 넣어 둘 수 있어요";
export const EDIT_ROOM_LABEL = "편집 중인 방";
export const STORAGE_TITLE = "보관함";
/** 상점에서 가구를 사고 넘어왔다는 표시(/room/edit?from=shop). 방금 산 가구를 놓으러 온 것이라 보관함을 펴 둔 채로 연다 */
export const EDIT_FROM_SHOP = "shop";
export const EDIT_ROOM_AREA_TEST_ID = "room-edit-area";
const NO_ROOM_NOTICE = "놓을 빈자리가 없어요. 다른 가구를 옮기거나 넣어 둔 뒤 다시 눌러 주세요.";
const NO_TURN_NOTICE = "돌릴 자리가 없어요. 주변을 비운 뒤 다시 눌러 주세요.";
const STORE_AWAY_BLOCK_TEXT: Record<StoreAwayBlock, string> = {
  WALL_OBJECT: "예산 보드·출금 캘린더는 옮기기만 할 수 있어요.",
  UNKNOWN_FURNITURE: "보유 정보를 확인할 수 없는 가구예요.",
};
const HOME_ROUTE = "/";
const LOAD_ERROR = "방 정보를 불러오지 못했어요.";
/** 보관함 타일 그림. 64pt 타일 안의 4px 스케일 밖 크기라 style 로 준다(상점 타일과 같은 방식) */
const TRAY_SPRITE_SIZE = 48;
const TRAY_COLUMNS = 4;
/** 말풍선 크기를 재기 전 첫 렌더에서 쓰는 어림값. 잰 뒤에는 실제 크기로 자리를 다시 잡는다 */
const BUBBLE_SIZE_GUESS: SceneSize = { width: 236, height: 60 };

type RoomEditScreenProps = {
  /** 보관함을 펴 둔 채로 연다(상점에서 가구를 사고 넘어왔을 때) */
  openStorage?: boolean;
};

/**
 * 방 꾸미기 화면 (홈 '꾸미기' → /room/edit). 가구·벽 오브젝트를 드래그로 옮긴다(스냅·겹침 판정은 RoomScene).
 * 방 조회와 보유 목록을 받은 뒤 편집 사본(draft)을 만든다. 완료는 전체 배치 PUT 한 번으로 저장한 뒤 확정하고, 취소(뒤로가기 포함)는 사본을 버린다.
 * 필수 가구도 편집 중에는 보관할 수 있고, 완료 시 소파·TV·식탁·커피테이블 각각 1개를 서버가 검사한다. 실패하면 사본을 유지한다(useRoomEditor).
 * 2026-09-21: 산 가구를 꺼내 놓는 보관함과, 고른 가구의 '방향 바꾸기'·'넣어 두기'를 더했다(사용자 결정). 보관함은 보유 목록에서
 * 사본에 없는 가구이고, 넣어 둔 가구는 저장할 때 설치 해제로 나간다.
 *
 * 배치(2026-09-21 사용자 결정): **방을 최대한 크게 쓴다.** 전에는 방 아래에 안내·선택 동작·보관함·취소/완료가 세로로 쌓여
 * 방이 남는 자리에 줄어들어 들어갔고, 방이 작을수록 반 칸 격자에 맞춰 끄는 조작이 어려웠다.
 * - 취소/완료는 헤더로 올린다(뒤로 = 취소, 오른쪽 = 완료). 하단 버튼 줄이 없어진다
 * - 고른 가구의 동작은 그 가구 옆 말풍선으로 띄운다. 시트로 올리면 방금 고른 가구나 앞쪽 바닥이 가려진다
 * - 보관함은 하단 손잡이 한 줄로 접어 두고 누르면 시트로 올라온다. 가구를 고르면 시트를 내려 놓인 자리를 바로 보여 준다.
 *   시트는 끌지 않고 눌러서만 여닫는다 — 방 캔버스의 가구 드래그와 제스처가 부딪히지 않게
 * - 방은 cover 가 아니라 contain 으로 맞춘다. 잘리는 바닥이 생기면 그 칸에는 가구를 놓을 수 없다
 * - 방·목록 조회가 실패하면 방 아래 한 줄에서 다시 시도한다(보관함 시트를 열지 않아도 보이게)
 * 카메라는 드래그와 겹치지 않게 1배로 잠근다. Pencil PAGE-10 방 꾸미기 (HTF8Q, 2026-09-15) 와 배치가 달라졌다 — Pencil 미대조.
 */
function RoomEditScreen({ openStorage = false }: RoomEditScreenProps) {
  const router = useRouter();
  const editor = useRoomEditor();
  usePreventRemove(editor.saving, () => {});
  const placements = useRoomStore(selectPlacements);
  const selectedId = useRoomStore((s) => s.selectedId);
  const cancelEdit = useRoomStore((s) => s.cancelEdit);
  const placeItem = useRoomStore((s) => s.placeItem);
  const removeItem = useRoomStore((s) => s.removeItem);
  const flipItem = useRoomStore((s) => s.flipItem);
  const [roomArea, setRoomArea] = React.useState({ width: 0, height: 0 });
  const [notice, setNotice] = React.useState<string | null>(null);
  const [storageOpen, setStorageOpen] = React.useState(openStorage);

  const handleRoomAreaLayout = React.useCallback((event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    setRoomArea({ width: Math.round(width), height: Math.round(height) });
  }, []);

  const roomWidth = roomArea.width > 0 && roomArea.height > 0 ? containSceneWidth(roomArea.width, roomArea.height) : 0;
  const selected = selectedId === null ? null : (placements.find((placement) => placement.itemId === selectedId) ?? null);
  const stored = storedFurnitures(editor.owned ?? [], placements);
  // 저장 중이거나 아직 방·목록을 못 받았으면 편집 조작을 막는다
  const busy = editor.saving || !editor.ready;
  const leftAfterSave = React.useRef(false);
  // 저장 잠금이 해제되어 내비게이션 차단도 풀린 렌더에서만 이동한다.
  React.useEffect(() => {
    if (!editor.completed || leftAfterSave.current) return;
    leftAfterSave.current = true;
    if (router.canGoBack()) router.back();
    else router.replace(HOME_ROUTE);
  }, [editor.completed, router]);

  const leave = () => {
    if (router.canGoBack()) router.back();
    else router.replace(HOME_ROUTE);
  };
  const cancel = () => {
    if (useRoomStore.getState().saving) return;
    cancelEdit();
    leave();
  };
  const done = () => {
    setNotice(null);
    void editor.submit();
  };

  const placeFromStorage = (furniture: StoredFurniture) => {
    const { draft } = useRoomStore.getState();
    if (!draft || useRoomStore.getState().saving) return;
    // 놓였든 빈자리가 없든 시트를 내린다 — 놓인 가구도, 빈자리가 없다는 안내도 시트 뒤의 방에 보인다.
    setStorageOpen(false);
    const placement = placeNewItem(draft, furniture.itemId, furniture.userFurnitureId);
    if (!placement) {
      setNotice(NO_ROOM_NOTICE);
      return;
    }
    setNotice(null);
    placeItem(placement);
  };
  const flipSelected = () => {
    if (selectedId === null) return;
    setNotice(flipItem(selectedId) ? null : NO_TURN_NOTICE);
  };
  const storeSelected = () => {
    if (selectedId === null) return;
    const selected = useRoomStore.getState().draft?.find((item) => item.itemId === selectedId);
    if (!selected || storeAwayBlock(selected, editor.owned ?? undefined) !== null) return;
    setNotice(null);
    removeItem(selectedId);
  };

  // 안내 한 줄. 저장 실패(서버 문구) > 방금 동작의 안내 > (아무것도 안 골랐을 때) 사용법 순으로 하나만 보여 준다.
  const status: StatusLine | null = editor.error !== null
    ? { text: editor.error, tone: "error" }
    : notice !== null
      ? { text: notice, tone: "notice" }
      : selected === null
        ? { text: EDIT_HINT, tone: "hint" }
        : null;

  return (
    <View className="flex-1 bg-background">
      <ScreenHeader
        title={EDIT_TITLE}
        onBack={cancel}
        // 방을 헤더 바로 아래부터 쓴다(헤더 기본 아래 여백 24 를 없앤다)
        className="mb-0"
        right={
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="편집 완료"
            accessibilityState={{ disabled: busy, busy: editor.saving }}
            hitSlop={10}
            disabled={busy}
            onPress={done}
          >
            <Text className={cn("text-label", busy ? "text-card-foreground" : "text-primary")}>
              {editor.saving ? "저장하는 중" : "완료"}
            </Text>
          </Pressable>
        }
      />
      {/* 남은 영역 안에 방 전체가 들어가게 맞춘다(contain). 바닥이 잘리면 그 칸에는 가구를 놓을 수 없다 */}
      <View
        className="flex-1 items-center justify-center"
        collapsable={false}
        onLayout={handleRoomAreaLayout}
        pointerEvents={busy ? "none" : "auto"}
        testID={EDIT_ROOM_AREA_TEST_ID}
      >
        <RoomView
          accessibilityLabel={EDIT_ROOM_LABEL}
          locked
          width={roomWidth > 0 ? roomWidth : undefined}
          panels={(width) =>
            selected === null ? null : (
              <SelectionBubble
                selected={selected}
                owned={editor.owned ?? undefined}
                canvasWidth={width}
                disabled={busy}
                onFlip={flipSelected}
                onStoreAway={storeSelected}
              />
            )
          }
        />
        {status === null ? null : <StatusPill status={status} />}
      </View>
      {editor.loadError ? <LoadErrorRow onRetry={editor.retry} /> : null}
      <StorageHandle count={editor.ready ? stored.length : null} disabled={editor.saving} onPress={() => setStorageOpen(true)} />
      <BottomSheet visible={storageOpen} onClose={() => setStorageOpen(false)} closeLabel="보관함 닫기">
        <StorageSheet
          stored={stored}
          pending={!editor.ready && !editor.loadError}
          failed={editor.loadError}
          retrying={!editor.ready && !editor.loadError}
          disabled={busy}
          onRetry={editor.retry}
          onPlace={placeFromStorage}
        />
      </BottomSheet>
    </View>
  );
}

type StatusLine = { text: string; tone: "hint" | "notice" | "error" };

// 방 위쪽에 뜨는 안내 한 줄. 방을 가리지 않게 작게 두고, 가구를 끄는 손가락을 가로채지 않도록 터치는 받지 않는다.
function StatusPill({ status }: { status: StatusLine }) {
  const error = status.tone === "error";

  return (
    <View className="absolute left-6 right-6 top-3 items-center" pointerEvents="none" accessibilityLiveRegion="polite">
      <View className="flex-row items-center gap-1.5 rounded-2xl bg-card px-4 py-2 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
        {status.tone === "hint" ? null : <Icon as={CircleAlert} size={16} className={error ? "text-destructive" : "text-card-foreground"} />}
        <Text className={cn("shrink text-caption", error ? "text-destructive" : "text-card-foreground")}>{status.text}</Text>
      </View>
    </View>
  );
}

type SelectionBubbleProps = {
  selected: Placement;
  owned: readonly UserFurniture[] | undefined;
  /** 방 캔버스 폭(pt). 말풍선은 캔버스와 같은 크기의 레이어에 놓인다 */
  canvasWidth: number;
  disabled: boolean;
  onFlip: () => void;
  onStoreAway: () => void;
};

// 방에서 고른 것 하나에 대한 동작을 그 가구 옆에 띄운다. 벽 기능 오브젝트는 돌리지도 넣어 두지도 않고,
// 보유 정보를 모르는 가구는 넣어 두지 못한다 — 막힌 이유를 글로 적는다. 필수 가구는 넣어 둘 수 있고 개수는 저장할 때 서버가 검사한다.
// 자리는 가구 아래가 기본이고 넘치면 위로 올린다(model.placeBubble).
function SelectionBubble({ selected, owned, canvasWidth, disabled, onFlip, onStoreAway }: SelectionBubbleProps) {
  const [size, setSize] = React.useState<SceneSize | null>(null);
  const name = owned?.find((furniture) => furniture.userFurnitureId === selected.userFurnitureId)?.name ?? roomItemName(selected.itemId);
  const flippable = !isWallItemId(selected.itemId);
  const block = storeAwayBlock(selected, owned);

  const view = placementView(selected);
  const target = sceneRectToCanvas(getSpriteRect(selected.anchor, view.size, view.anchor), getSceneScale(canvasWidth));
  const spot = placeBubble(target, size ?? BUBBLE_SIZE_GUESS, getCanvasSize(canvasWidth));

  const handleLayout = (event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    setSize((current) => (current !== null && current.width === width && current.height === height ? current : { width, height }));
  };

  return (
    <View
      onLayout={handleLayout}
      // 자리는 고른 가구에 따라 매번 달라지는 값이라 style 로 준다. 크기를 재기 전 첫 프레임은 감춰 어림 자리에서 튀지 않게 한다.
      style={{ position: "absolute", left: spot.x, top: spot.y, opacity: size === null ? 0 : 1 }}
      className="gap-1 rounded-2xl bg-card p-2 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none"
    >
      <View className="flex-row gap-2">
        <Button
          variant="secondary"
          size="sm"
          className="h-button-md rounded-lg sm:h-button-md"
          onPress={onFlip}
          disabled={disabled || !flippable}
          accessibilityState={{ disabled: disabled || !flippable }}
          accessibilityLabel={`${name} 방향 바꾸기`}
        >
          <Icon as={FlipHorizontal2} size={16} className="text-secondary-foreground" />
          <Text>방향 바꾸기</Text>
        </Button>
        <Button
          variant="secondary"
          size="sm"
          className="h-button-md rounded-lg sm:h-button-md"
          onPress={onStoreAway}
          disabled={disabled || block !== null}
          accessibilityState={{ disabled: disabled || block !== null }}
          accessibilityLabel={`${name} 넣어 두기`}
        >
          <Icon as={Archive} size={16} className="text-secondary-foreground" />
          <Text>넣어 두기</Text>
        </Button>
      </View>
      {block === null ? null : <Text className="px-1 text-caption text-card-foreground">{STORE_AWAY_BLOCK_TEXT[block]}</Text>}
    </View>
  );
}

// 방·보유 목록 조회 실패. 보관함 시트를 열지 않아도 다시 시도할 수 있게 방 아래 한 줄로 둔다
function LoadErrorRow({ onRetry }: { onRetry: () => void }) {
  return (
    <View className="flex-row items-center gap-2 px-6 pt-2" accessibilityLiveRegion="polite">
      <Icon as={CircleAlert} size={16} className="text-destructive" />
      <Text className="flex-1 text-caption text-destructive">{LOAD_ERROR}</Text>
      <Button variant="ghost" size="sm" className="h-button-md sm:h-button-md" onPress={onRetry}>
        <Text>다시 시도</Text>
      </Button>
    </View>
  );
}

type StorageHandleProps = {
  /** 보관 중인 가구 수. 아직 모르면(받는 중·실패) null */
  count: number | null;
  disabled: boolean;
  onPress: () => void;
};

// 접어 둔 보관함. 방 아래 한 줄만 차지하고, 누르면 시트가 올라온다.
function StorageHandle({ count, disabled, onPress }: StorageHandleProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={count === null ? `${STORAGE_TITLE} 열기` : `${STORAGE_TITLE} 열기, ${count}개`}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      className="flex-row items-center gap-2 border-t border-border bg-card px-6 pb-8 pt-4 active:opacity-80"
    >
      <Icon as={Archive} size={20} className="text-foreground" />
      <Text className="text-label text-foreground">{STORAGE_TITLE}</Text>
      {count === null ? null : <Text className="text-caption tabular-nums text-card-foreground">{count}개</Text>}
      <View className="flex-1" />
      <Icon as={ChevronUp} size={20} className="text-card-foreground" />
    </Pressable>
  );
}

type StorageSheetProps = {
  stored: StoredFurniture[];
  pending: boolean;
  failed: boolean;
  retrying: boolean;
  disabled: boolean;
  onRetry: () => void;
  onPlace: (furniture: StoredFurniture) => void;
};

const TRAY_SKELETON = [1, 2, 3, 4];

// 산 뒤 아직 방에 없는 가구. 누르면 빈 칸에 놓이고 골라진 상태가 되어 바로 끌어 옮길 수 있다.
function StorageSheet({ stored, pending, failed, retrying, disabled, onRetry, onPlace }: StorageSheetProps) {
  return (
    <View className="gap-3 pt-5">
      <View className="flex-row items-center justify-between px-6">
        <Text className="text-h3 text-foreground" accessibilityRole="header">
          {STORAGE_TITLE}
        </Text>
        {pending || failed ? null : <Text className="text-caption tabular-nums text-card-foreground">{stored.length}개</Text>}
      </View>
      {pending ? (
        <View className="flex-row gap-3 px-6" accessible accessibilityLabel="보관함을 불러오는 중">
          {TRAY_SKELETON.map((key) => (
            <Skeleton key={key} className="h-16 w-16 rounded-xl" />
          ))}
        </View>
      ) : failed ? (
        <View className="flex-row items-center gap-2 px-6" accessibilityLiveRegion="polite">
          <Text className="flex-1 text-caption text-card-foreground">보관함을 불러오지 못했어요.</Text>
          <Button variant="ghost" size="sm" className="h-button-md sm:h-button-md" onPress={onRetry} disabled={retrying}>
            <Text>다시 시도</Text>
          </Button>
        </View>
      ) : stored.length === 0 ? (
        <Text className="px-6 text-body-sm text-card-foreground">보관 중인 가구가 없어요. 상점에서 산 가구가 여기에 생겨요.</Text>
      ) : (
        <FlatList
          className="max-h-72"
          data={stored}
          numColumns={TRAY_COLUMNS}
          keyExtractor={(furniture) => String(furniture.userFurnitureId)}
          columnWrapperClassName="gap-3 overflow-visible"
          contentContainerClassName="gap-3 overflow-visible px-6"
          // 그림자가 셀의 원래 경계 밖으로 나가므로 Android에서도 셀 경계로 그림을 제거하지 않는다.
          removeClippedSubviews={false}
          renderItem={({ item }) => <StoredTile furniture={item} disabled={disabled} onPress={onPlace} />}
        />
      )}
      {stored.some((item) => item.stickerAttached) ? (
        <Text className="px-6 text-caption text-card-foreground">압류 딱지는 다시 설치한 뒤 제거할 수 있어요.</Text>
      ) : null}
    </View>
  );
}

function StoredTile({ furniture, disabled, onPress }: { furniture: StoredFurniture; disabled: boolean; onPress: (furniture: StoredFurniture) => void }) {
  const thumbnail = roomItemThumbnail(furniture.assetKey);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${furniture.name}${furniture.stickerAttached ? ", 압류 딱지 부착" : ""}, 방에 놓기`}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={() => onPress(furniture)}
      className="w-16 items-center gap-1 overflow-visible active:opacity-80"
    >
      <View className="h-16 w-16 items-center justify-center overflow-visible rounded-xl bg-muted" accessible={false}>
        {thumbnail === null ? (
          <Icon as={Sofa} size={24} className="text-card-foreground" />
        ) : (
          <FurnitureThumbnail source={thumbnail} geometry={roomItemThumbnailGeometry(furniture.assetKey)} size={TRAY_SPRITE_SIZE} />
        )}
        {furniture.stickerAttached ? <Text className="absolute bottom-0 rounded bg-destructive px-1 text-caption text-white">압류</Text> : null}
      </View>
      <Text className="text-caption text-card-foreground" numberOfLines={1}>
        {furniture.name}
      </Text>
    </Pressable>
  );
}

export { RoomEditScreen };
