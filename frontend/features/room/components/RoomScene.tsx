import {
  Canvas,
  CatmullRomCubicSampling,
  FilterMode,
  Group,
  Image as SkiaImage,
  MipmapMode,
  Path,
  Skia,
  type SkImage,
} from "@shopify/react-native-skia";
import { useColorScheme } from "nativewind";
import * as React from "react";
import { View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { runOnJS, useAnimatedReaction, useDerivedValue, useSharedValue } from "react-native-reanimated";

import { Skeleton } from "@/components/ui/skeleton";
import { CHARACTER_IDLE, COACH_CAT, ROOM_FLOOR, SEIZURE_STICKER } from "@/features/room/assets";
import { useFurnitures, useRoom } from "@/features/room/api/queries";
import { stickerGeometry, stickerPlacements } from "@/features/room/stickers";
import { penaltyGeometry, PENALTY_SPRITES, type PenaltyGeometry } from "@/features/room/penalties";
import { loadSceneImage } from "@/features/room/sceneImages";
import { readCamera, useRoomCamera } from "@/features/room/camera";
import { FURNITURE, WALL_ITEMS, isWallItemId, type RoomItemId } from "@/features/room/catalog";
import {
  canvasPointToScene,
  depthIndexAt,
  depthKey,
  getCanvasSize,
  getSceneScale,
  getSpriteRect,
  hitTestTopmost,
  sceneRectToCanvas,
  sortByDepth,
  type ScenePoint,
  type Surface,
} from "@/features/room/model";
import {
  anchorToCell,
  cellAnchor,
  cellToScene,
  footprintOutline,
  halfSpan,
  isGridPlacementValid,
  snapToCell,
  HALF_PER_CELL,
  type GridCell,
  type GridFootprint,
  type GridPlacement,
  type SurfaceDef,
} from "@/features/room/grid";
import {
  CHARACTER_MOTION,
  CHARACTER_SIZE,
  COACH_CAT_ANCHOR,
  COACH_CAT_FOOTPRINT,
  COACH_CAT_RECT,
  FLOOR_POLYGON,
  SURFACES,
  getSeatPoint,
  getWalkBlockers,
  isPlaceableOn,
  placementView,
  type Placement,
  type PlacementView,
} from "@/features/room/scene";
import { findOutfit } from "@/features/room/outfits";
import { useNotifySceneReady } from "@/features/room/sceneReady";
import { selectIsEditing, selectPlacements, useRoomStore } from "@/features/room/store";
import { useCharacterWalker, type CharacterWalker } from "@/features/room/useCharacterWalker";
import { useCoachCatMotion } from "@/features/room/useCoachCatMotion";
import { getColors } from "@/lib/theme";

// 바닥 1장 + 벽 오브젝트(보드·캘린더·벽 장식) + 러그 + 가구를 그린다. 가구는 발끝 y 기준 painter's algorithm 으로 정렬하고 캐릭터는 정렬된 가구 사이에 끼운다.
// 벽 오브젝트는 벽에 붙어 있어 깊이 정렬에 끼지 않고 바닥 바로 위, 가구보다 먼저 그린다. 러그는 바닥에 깔려 그다음이다(캐릭터가 밟고 지나간다).
// 캐릭터는 매 프레임 움직이므로 JSX 를 재정렬하는 대신 캐릭터가 들어갈 위치(depthIndex)만 워크릿에서 계산해
// 그 값이 바뀔 때만 React 상태를 갱신한다(가구 경계를 넘을 때만 리렌더).
// 확대·이동: RoomView 가 가진 카메라(셰어드 값)를 최상위 Group transform 으로 걸어 씬을 통째로 옮긴다. 원본을 다시 그리므로 확대해도 선명하다.
// 편집 모드: 캔버스 위 Pan 제스처로 가구·벽 오브젝트를 끌어 옮긴다. 가구는 바닥 격자, 벽 오브젝트는 자기 벽 격자에 스냅한다.
// 끌리는 것은 맨 앞에 그리고 위치는 셰어드 값으로 따라가며, 손을 떼면 스토어(draft)에 반영되고 정렬이 다시 계산된다.

const FLOOR_SURFACE = SURFACES.FLOOR;

/**
 * 방에 늘 쓰이는 스프라이트. 한 장씩 준비되는 대로 그리면 바닥이 먼저 깔리고 가구가 하나씩 튀어나와
 * 실제보다 오래 걸리는 것처럼 보였다(사용자 지적 2026-09-20). 이것과 놓인 가구 그림이 다 준비될 때까지 기다렸다가 방을 통째로 보여 준다.
 * 가구 그림은 146장(약 27MB)이라 전부 데우지 않고 놓인 것만 읽는다(sceneFurnitureSprites).
 */
const BASE_SPRITES: readonly number[] = [ROOM_FLOOR, CHARACTER_IDLE, COACH_CAT, SEIZURE_STICKER, ...Object.values(WALL_ITEMS).map((item) => item.sprite)];

/**
 * 놓인 가구 그림. `current` 는 지금 방향 그림이라 방을 보여 주기 전에 기다리고,
 * `turned` 는 편집 중에만 미리 읽는 반대 방향 그림이다 — '방향 바꾸기'를 눌렀을 때 그림이 비지 않게 한다.
 */
function sceneFurnitureSprites(placements: readonly Placement[], editing: boolean): { current: number[]; turned: number[] } {
  const current = new Set<number>();
  const turned = new Set<number>();
  for (const placement of placements) {
    if (isWallItemId(placement.itemId)) continue;
    current.add(placementView(placement).sprite);
    if (editing) for (const view of Object.values(FURNITURE[placement.itemId].views)) turned.add(view.sprite);
  }
  return { current: [...current], turned: [...turned].filter((source) => !current.has(source)) };
}

/**
 * 스프라이트 한 장을 불러 위로 넘기기만 한다(그리지 않는다).
 * Skia는 부르는 곳마다 따로 읽어들이므로(캐시가 없다) 이 로더를 계속 띄워 둔 채
 * 읽어 온 이미지를 그리는 쪽에 넘긴다 — 그리는 쪽에서 다시 부르면 처음부터 다시 읽어 또 하나씩 튀어나온다.
 */
function SpriteLoader({ source, onLoad }: { source: number; onLoad: (source: number, image: SkImage) => void }) {
  React.useEffect(() => {
    let mounted = true;
    void loadSceneImage(source).then((image) => {
      if (mounted && image) onLoad(source, image);
    });
    return () => { mounted = false; };
  }, [onLoad, source]);
  return null;
}

type SceneImages = ReadonlyMap<number, SkImage>;

/**
 * 방 스프라이트를 한 번씩만 읽어 모아 둔다. `loaders` 는 화면에 계속 띄워 둬야 이미지가 살아 있다.
 * `required` 는 방을 보여 주기 전에 기다리는 그림, `optional` 은 입고 있는 옷 세트처럼 나중에 정해지는 그림이다 —
 * 방을 보여 주는 조건(`ready`)에 넣지 않아 옷 그림을 기다리느라 방 전체가 늦어지지 않게 한다(FR-GAM-01 진입 1초). 준비되기 전에는 기본 차림으로 그린다.
 */
function useSceneImages(required: readonly number[], optional: readonly number[]) {
  const [images, setImages] = React.useState<SceneImages>(() => new Map());
  const handleLoad = React.useCallback((source: number, image: SkImage) => {
    setImages((current) => {
      if (current.get(source) === image) return current;
      const next = new Map(current);
      next.set(source, image);
      return next;
    });
  }, []);
  const loaders = [...new Set([...required, ...optional])].map((source) => <SpriteLoader key={source} source={source} onLoad={handleLoad} />);
  return { images, loaders, ready: required.every((source) => images.has(source)) };
}

// Skia 기본 샘플링은 밉맵 없는 linear 라 크기 차이가 큰 그림이 뭉개진다.
// 스프라이트 원본은 그려지는 크기의 3~5배라 밉맵으로 줄이고, 바닥(768px)은 화면 픽셀보다 작아 늘어나므로 cubic 으로 윤곽을 지킨다.
const SPRITE_SAMPLING = { filter: FilterMode.Linear, mipmap: MipmapMode.Linear } as const;
const FLOOR_SAMPLING = CatmullRomCubicSampling;

/** 그릴 준비를 마친 배치. item 은 방향·붙은 벽을 반영한 그림과 발자국이다(scene.ts placementView) */
type PlacedItem = {
  id: RoomItemId;
  anchor: ScenePoint;
  layer: number;
  item: PlacementView;
  surface: Surface;
  sticker: ReturnType<typeof stickerGeometry>;
  penalty: PenaltyGeometry | null;
};

function toPlaced(placement: Placement, stickerAttached: boolean, overEnvelopeIds: readonly number[]): PlacedItem {
  const { itemId, anchor } = placement;
  const fixedWall = isWallItemId(itemId) ? WALL_ITEMS[itemId].surface : undefined;
  return { id: itemId, anchor, layer: placement.layer ?? 0, item: placementView(placement), surface: placement.surface ?? fixedWall ?? "FLOOR",
    sticker: stickerAttached ? stickerGeometry(placement) : null, penalty: penaltyGeometry(placement, overEnvelopeIds) };
}

/**
 * 코치 고양이도 바닥의 가구와 같은 발끝 y 기준 깊이 정렬에 끼운다 — 소파 뒤로 가려지거나 캐릭터 앞에 서는 것이 자연스러워야 한다.
 * 가구가 아니라 편집 모드에서 끌리지 않고(hit test 에 넣지 않는다) 자리는 scene.ts 의 상수다.
 */
const COACH_CAT_NODE = { id: "coach_cat", anchor: COACH_CAT_ANCHOR, layer: 0 } as const;
type DepthNode = PlacedItem | typeof COACH_CAT_NODE;

function isCoachCat(node: DepthNode): node is typeof COACH_CAT_NODE {
  return node.id === COACH_CAT_NODE.id;
}

type RoomSceneProps = {
  /** 캔버스 폭(pt). 높이는 씬 비율로 정해진다. */
  width: number;
};

function RoomScene({ width }: RoomSceneProps) {
  const { height } = getCanvasSize(width);
  const scale = getSceneScale(width);
  const camera = useRoomCamera();
  // 입고 있는 옷 세트. 카탈로그에 없는 assetKey 뿐이거나 아직 안 왔으면 null 이라 기본 차림으로 그린다.
  const room = useRoom();
  const outfit = React.useMemo(() => findOutfit(room.data?.equipped ?? []), [room.data]);
  const outfitSprites = React.useMemo(() => (outfit ? [outfit.standing, outfit.sitting] : []), [outfit]);

  const placements = useRoomStore(selectPlacements);
  const isEditing = useRoomStore(selectIsEditing);
  const owned = useFurnitures(undefined, isEditing);
  const saving = useRoomStore((state) => state.saving);
  const selectedId = useRoomStore((s) => s.selectedId);
  const select = useRoomStore((s) => s.select);
  const moveItem = useRoomStore((s) => s.moveItem);

  const furnitureSprites = React.useMemo(() => sceneFurnitureSprites(placements, isEditing), [placements, isEditing]);
  const requiredSprites = React.useMemo(() => [...BASE_SPRITES, ...furnitureSprites.current], [furnitureSprites]);
  // 페널티 로드 실패·지연은 방의 ready 조건에 영향을 주지 않는다.
  const optionalSprites = React.useMemo(() => [...outfitSprites, ...furnitureSprites.turned, ...PENALTY_SPRITES], [outfitSprites, furnitureSprites]);
  const { images, loaders, ready } = useSceneImages(requiredSprites, optionalSprites);
  // 한 번 보여 준 방은 다시 스켈레톤으로 돌리지 않는다 — 보관함에서 새 가구를 꺼내면 그 그림만 읽히는 동안 잠깐 비어 있다.
  const [revealed, setRevealed] = React.useState(false);
  if (ready && !revealed) setRevealed(true);
  useNotifySceneReady(ready || revealed);
  const floor = images.get(ROOM_FLOOR);
  const { colorScheme } = useColorScheme();
  const themeColors = getColors(colorScheme);
  const cameraTransform = useDerivedValue(() => [{ translateX: camera.tx.value }, { translateY: camera.ty.value }, { scale: camera.scale.value }]);

  const placed = React.useMemo(() => {
    const source = isEditing && owned.data ? owned.data.map((item) => item.serverState) : room.data?.furnitures ?? [];
    const stamped = new Set(stickerPlacements(placements, source, isEditing));
    return placements.map((placement) => {
      const installed = isEditing || source.some((item) => item.assetKey === placement.itemId && item.placementStatus === "FLOOR");
      return toPlaced(placement, stamped.has(placement), installed ? room.data?.overEnvelopeIds ?? [] : []);
    });
  }, [placements, isEditing, owned.data, room.data?.furnitures, room.data?.overEnvelopeIds]);
  const wallItems = React.useMemo(() => placed.filter((p) => p.surface !== "FLOOR"), [placed]);
  const rugs = React.useMemo(() => placed.filter((p) => p.surface === "FLOOR" && p.item.flat), [placed]);
  const sorted = React.useMemo<readonly PlacedItem[]>(
    () => sortByDepth(placed.filter((p) => p.surface === "FLOOR" && !p.item.flat)),
    [placed]
  );
  // 그리는 순서. 가구 사이에 코치 고양이를 끼워 정렬한 것이라, 캐릭터가 들어갈 위치(depthIndex)도 이 순서 기준이다.
  const depthNodes = React.useMemo<readonly DepthNode[]>(() => sortByDepth<DepthNode>([...sorted, COACH_CAT_NODE]), [sorted]);
  const sortedKeys = React.useMemo(() => depthNodes.map(depthKey), [depthNodes]);
  // 캐릭터가 피해 갈 발자국 — 가구(벽 오브젝트와 러그는 빠진다)와 코치 고양이 자리.
  const footprints = React.useMemo(() => [...getWalkBlockers(placements), COACH_CAT_FOOTPRINT], [placements]);
  // 자동 보행은 편집 중에만 끈다 — 가구를 끌 때 캐릭터가 돌아다니면 방해된다(2026-09-09 결정의 이유, 2026-09-21 되켬).
  // 앉기는 앉은 그림이 있는 세트를 입었을 때만 한다. 기본 차림은 앉은 그림이 없어 걷기만 한다.
  const seat = React.useMemo(() => (outfit ? getSeatPoint(placements) : null), [outfit, placements]);
  const walker = useCharacterWalker({ polygon: FLOOR_POLYGON, blocked: footprints, walking: !isEditing, seat });

  // 앉고 서는 것은 그림이 바뀌는 일이라(셰어드 값만으로는 Skia 이미지가 안 바뀐다) 바뀔 때만 React 상태로 올린다.
  const [seated, setSeated] = React.useState(false);
  useAnimatedReaction(
    () => walker.sitting.value === 1,
    (next, previous) => {
      if (next !== previous) runOnJS(setSeated)(next);
    }
  );
  // 앉은 그림이 아직 안 읽혔으면 같은 세트의 서 있는 그림으로 버틴다 — 앉는 순간 기본 차림으로 튀지 않게.
  const seatedSprite = outfit && seated ? images.get(outfit.sitting) : undefined;
  const standingSprite = outfit ? images.get(outfit.standing) : undefined;
  const character = seatedSprite ?? standingSprite ?? images.get(CHARACTER_IDLE);

  const [depthIndex, setDepthIndex] = React.useState(() => depthIndexAt(sortedKeys, CHARACTER_MOTION.start.y));
  useAnimatedReaction(
    () => depthIndexAt(sortedKeys, walker.y.value),
    (next, previous) => {
      if (next !== previous) runOnJS(setDepthIndex)(next);
    },
    [sortedKeys]
  );

  // 드래그 상태. draggingId 는 리렌더(그리기 순서)를 위해 React 상태, 위치는 매 프레임 갱신되므로 셰어드 값.
  const [draggingId, setDraggingId] = React.useState<RoomItemId | null>(null);
  const dragX = useSharedValue(0);
  const dragY = useSharedValue(0);
  /** 놓을 수 있는 자리면 1. 겹치거나 면 밖이면 0 이 되어 반투명 + 빨간 칸으로 알린다. */
  const dragValid = useSharedValue(1);
  const dragStart = React.useRef<{ id: RoomItemId; surface: Surface; footprint: GridFootprint; from: GridCell; others: GridPlacement[] } | null>(
    null
  );

  const pan = React.useMemo(
    () =>
      Gesture.Pan()
        .enabled(isEditing && !saving)
        .runOnJS(true)
        .minDistance(0)
        .onBegin((event) => {
          const point = canvasPointToScene({ x: event.x, y: event.y }, readCamera(camera), scale);
          // 그리는 순서(벽 → 러그 → 가구)대로 넘겨 가장 앞의 것을 잡는다.
          const all = [...wallItems, ...rugs, ...sorted];
          const id = hitTestTopmost(point, all.map((p) => ({ id: p.id, rect: getSpriteRect(p.anchor, p.item.size, p.item.anchor) })));
          select(id);
          if (!id) return;
          const target = all.find((p) => p.id === id)!;
          const def = SURFACES[target.surface];
          dragStart.current = {
            id,
            surface: target.surface,
            footprint: target.item.grid,
            from: anchorToCell(def, target.anchor, target.item.grid),
            // 같은 면·같은 층의 다른 것과만 겹침을 본다 — 벽 오브젝트와 가구는 면이 달라, 러그와 가구는 층이 달라 겹쳐도 된다.
            others: all
              .filter((p) => p.id !== id && p.surface === target.surface && p.item.flat === target.item.flat)
              .map((p) => ({ cell: anchorToCell(def, p.anchor, p.item.grid), footprint: p.item.grid })),
          };
          dragX.value = target.anchor.x;
          dragY.value = target.anchor.y;
          dragValid.value = 1;
          setDraggingId(id);
        })
        .onUpdate((event) => {
          const start = dragStart.current;
          if (!start) return;
          // 손가락이 짚은 씬 좌표를 그 면의 반 칸 자리로 스냅한다. 칸 단위라 확대 배율과 무관하게 같은 자리에 붙는다.
          // 막힌 자리로 미끄러뜨리지 않고 짚은 칸을 그대로 보여준 뒤, 놓을 수 없으면 그렇게 표시한다.
          const dragScale = scale * camera.scale.value;
          const def = SURFACES[start.surface];
          const origin = cellAnchor(def, start.from, start.footprint);
          const cell = snapToCell(
            def,
            { x: origin.x + event.translationX / dragScale, y: origin.y + event.translationY / dragScale },
            start.footprint
          );
          const anchor = cellAnchor(def, cell, start.footprint);
          dragX.value = anchor.x;
          dragY.value = anchor.y;
          dragValid.value = isGridPlacementValid(def, cell, start.footprint, start.others, (candidate) =>
            isPlaceableOn(start.surface, candidate, start.footprint)
          )
            ? 1
            : 0;
        })
        .onFinalize(() => {
          const start = dragStart.current;
          if (!start) return;
          // 놓을 수 없는 자리면 옮기지 않는다. 원래 칸으로 되돌아간다.
          if (dragValid.value) moveItem(start.id, { x: dragX.value, y: dragY.value });
          dragStart.current = null;
          setDraggingId(null);
          dragValid.value = 1;
        }),
    [isEditing, saving, scale, camera, wallItems, rugs, sorted, select, moveItem, dragX, dragY, dragValid]
  );

  React.useEffect(() => {
    if (!isEditing || saving) setDraggingId(null);
  }, [isEditing, saving]);

  const dragging = draggingId ? placed.find((p) => p.id === draggingId) ?? null : null;
  const stationaryWall = wallItems.filter((p) => p.id !== draggingId);
  const stationaryRugs = rugs.filter((p) => p.id !== draggingId);
  const stationary = depthNodes.filter((node) => node.id !== draggingId);
  const behind = stationary.slice(0, Math.min(depthIndex, stationary.length));
  const inFront = stationary.slice(behind.length);
  const highlightId = draggingId ?? (isEditing ? selectedId : null);
  const spriteProps = { scale, ringColor: themeColors.primary, images };
  const renderNode = (node: DepthNode) =>
    isCoachCat(node) ? (
      <CoachCatSprite key={node.id} scale={scale} image={images.get(COACH_CAT)} />
    ) : (
      <ItemSprite key={node.id} placed={node} highlighted={node.id === highlightId} {...spriteProps} />
    );

  // 로더는 두 갈래 모두에서 같은 자리에 둔다 — 자리가 바뀌면 다시 마운트되어 이미지를 또 읽는다.
  if (!ready && !revealed) {
    return (
      <>
        {loaders}
        <View style={{ width, height }}>
          <Skeleton className="h-full w-full" accessibilityLabel="방을 불러오는 중" />
        </View>
      </>
    );
  }

  return (
    <>
      {loaders}
      <GestureDetector gesture={pan}>
      <View style={{ width, height }} collapsable={false}>
        <Canvas style={{ width, height }}>
          <Group transform={cameraTransform}>
            {floor ? <SkiaImage image={floor} x={0} y={0} width={width} height={height} fit="cover" sampling={FLOOR_SAMPLING} /> : null}
            {stationaryWall.map((p) => (
              <ItemSprite key={p.id} placed={p} highlighted={p.id === highlightId} {...spriteProps} />
            ))}
            {stationaryRugs.map((p) => (
              <ItemSprite key={p.id} placed={p} highlighted={p.id === highlightId} {...spriteProps} />
            ))}
            {isEditing ? <GridOverlay scale={scale} color={themeColors.white} /> : null}
            {behind.map(renderNode)}
            <CharacterSprite walker={walker} scale={scale} image={character} />
            {inFront.map(renderNode)}
            {dragging ? (
              <DraggingSprite
                placed={dragging}
                anchorX={dragX}
                anchorY={dragY}
                valid={dragValid}
                blockedColor={themeColors.destructive}
                {...spriteProps}
              />
            ) : null}
          </Group>
        </Canvas>
      </View>
      </GestureDetector>
    </>
  );
}

type GridOverlayProps = { scale: number; color: string };

/** 한 면의 칸 선. 배치 단위는 반 칸이지만 선은 칸 단위로만 그린다 — 반 칸까지 그리면 선이 두 배가 되어 면이 읽히지 않는다. */
function gridLines(surface: SurfaceDef, scale: number) {
  const { cols, rows } = halfSpan(surface);
  const grid = Skia.PathBuilder.Make();
  const addLine = (from: ScenePoint, to: ScenePoint) => {
    grid.moveTo(from.x * scale, from.y * scale);
    grid.lineTo(to.x * scale, to.y * scale);
  };
  for (let col = 0; col <= cols; col += HALF_PER_CELL) {
    addLine(cellToScene(surface, { col, row: 0 }), cellToScene(surface, { col, row: rows }));
  }
  for (let row = 0; row <= rows; row += HALF_PER_CELL) {
    addLine(cellToScene(surface, { col: 0, row }), cellToScene(surface, { col: cols, row }));
  }
  return grid.detach();
}

function polygonPath(points: readonly ScenePoint[], scale: number) {
  const path = Skia.PathBuilder.Make();
  points.forEach((point, index) => {
    const x = point.x * scale;
    const y = point.y * scale;
    if (index === 0) path.moveTo(x, y);
    else path.lineTo(x, y);
  });
  path.close();
  return path.detach();
}

const WALL_SURFACES = [SURFACES.WALL_LEFT, SURFACES.WALL_RIGHT] as const;

/**
 * 편집 모드에서 바닥과 두 벽의 칸을 보여준다(벽 격자는 2026-09-15 사용자 요청).
 * 바닥 격자는 화면 밖까지 뻗어 있으므로 보이는 바닥 모양으로 잘라내고, 벽은 벽면 사각형으로 잘라낸다(윗변이 캔버스 위로 나간다).
 */
function GridOverlay({ scale, color }: GridOverlayProps) {
  const { floor, floorLines, walls } = React.useMemo(
    () => ({
      floor: polygonPath(FLOOR_POLYGON, scale),
      floorLines: gridLines(FLOOR_SURFACE, scale),
      walls: WALL_SURFACES.map((surface) => ({ clip: polygonPath(surface.quad, scale), lines: gridLines(surface, scale) })),
    }),
    [scale]
  );

  return (
    <>
      {walls.map((wall, index) => (
        <Group key={index} clip={wall.clip}>
          <Path path={wall.clip} style="fill" color={color} opacity={0.08} />
          <Path path={wall.lines} style="stroke" strokeWidth={1.5} color={color} opacity={0.45} />
        </Group>
      ))}
      <Group clip={floor}>
        <Path path={floor} style="fill" color={color} opacity={0.1} />
        <Path path={floorLines} style="stroke" strokeWidth={1.5} color={color} opacity={0.55} />
      </Group>
    </>
  );
}

/** 놓이는 칸을 그 면의 격자 모양(평행사변형) 그대로 그린다. origin 을 주면 그 기준점 위치로 옮겨 만든다. */
function outlinePath(surface: SurfaceDef, footprint: GridFootprint, scale: number, origin: ScenePoint = { x: 0, y: 0 }) {
  const path = Skia.PathBuilder.Make();
  footprintOutline(surface, footprint).forEach((point, index) => {
    const x = (origin.x + point.x) * scale;
    const y = (origin.y + point.y) * scale;
    if (index === 0) path.moveTo(x, y);
    else path.lineTo(x, y);
  });
  path.close();
  return path.detach();
}

type ItemSpriteProps = { placed: PlacedItem; scale: number; highlighted?: boolean; ringColor: string; images: SceneImages };

function ItemSprite({ placed, scale, highlighted = false, ringColor, images }: ItemSpriteProps) {
  const image = images.get(placed.item.sprite);
  const rect = React.useMemo(
    () => sceneRectToCanvas(getSpriteRect(placed.anchor, placed.item.renderSize, placed.item.renderAnchor), scale),
    [placed, scale]
  );
  const ring = React.useMemo(() => outlinePath(SURFACES[placed.surface], placed.item.grid, scale, placed.anchor), [placed, scale]);
  if (!image) return null;
  return (
    <>
      {highlighted ? (
        <Group>
          <Path path={ring} style="fill" color={ringColor} opacity={0.18} />
          <Path path={ring} style="stroke" strokeWidth={2} color={ringColor} opacity={0.9} />
        </Group>
      ) : null}
      <SkiaImage image={image} x={rect.x} y={rect.y} width={rect.width} height={rect.height} fit="contain" sampling={SPRITE_SAMPLING} />
      <PenaltySprite geometry={placed.penalty} scale={scale} images={images} />
      <StickerSprite geometry={placed.sticker} scale={scale} image={images.get(SEIZURE_STICKER)} />
    </>
  );
}

type DraggingSpriteProps = {
  placed: PlacedItem;
  scale: number;
  anchorX: { value: number };
  anchorY: { value: number };
  /** 1 이면 놓을 수 있는 자리, 0 이면 막힌 자리 */
  valid: { value: number };
  ringColor: string;
  blockedColor: string;
  images: SceneImages;
};

function PenaltySprite({ geometry, scale, images }: { geometry: PenaltyGeometry | null; scale: number; images: SceneImages }) {
  const image = geometry ? images.get(geometry.sprite) : undefined;
  if (!geometry || !image) return null;
  return <SkiaImage image={image} {...sceneRectToCanvas(geometry.rect, scale)} fit="fill" sampling={SPRITE_SAMPLING} />;
}

function StickerSprite({ geometry, scale, image }: { geometry: ReturnType<typeof stickerGeometry>; scale: number; image: SkImage | undefined }) {
  if (!geometry || !image) return null;
  const rect = sceneRectToCanvas(geometry.rect, scale);
  return (
    <Group origin={{ x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }} transform={[{ rotate: geometry.angle }]}>
      <SkiaImage image={image} {...rect} fit="contain" sampling={SPRITE_SAMPLING} />
    </Group>
  );
}

/** 끌리는 동안의 오브젝트. 위치는 셰어드 값에서 매 프레임 읽고, 놓일 칸을 그 면의 격자 모양 그대로 깔아 보여준다. */
function DraggingSprite({ placed, scale, anchorX, anchorY, valid, ringColor, blockedColor, images }: DraggingSpriteProps) {
  const image = images.get(placed.item.sprite);
  const { item } = placed;
  const rect = useDerivedValue(() =>
    sceneRectToCanvas(getSpriteRect({ x: anchorX.value, y: anchorY.value }, item.renderSize, item.renderAnchor), scale)
  );
  const x = useDerivedValue(() => rect.value.x);
  const y = useDerivedValue(() => rect.value.y);
  const ring = React.useMemo(() => outlinePath(SURFACES[placed.surface], item.grid, scale), [placed.surface, item, scale]);
  const ringTransform = useDerivedValue(() => [
    { translateX: anchorX.value * scale },
    { translateY: anchorY.value * scale },
  ]);
  const okFill = useDerivedValue(() => (valid.value ? 0.22 : 0));
  const okLine = useDerivedValue(() => (valid.value ? 0.95 : 0));
  const blockedFill = useDerivedValue(() => (valid.value ? 0 : 0.28));
  const blockedLine = useDerivedValue(() => (valid.value ? 0 : 0.95));
  const spriteOpacity = useDerivedValue(() => (valid.value ? 0.9 : 0.3));
  if (!image) return null;
  return (
    <>
      <Group transform={ringTransform}>
        <Path path={ring} style="fill" color={ringColor} opacity={okFill} />
        <Path path={ring} style="stroke" strokeWidth={2} color={ringColor} opacity={okLine} />
        <Path path={ring} style="fill" color={blockedColor} opacity={blockedFill} />
        <Path path={ring} style="stroke" strokeWidth={2} color={blockedColor} opacity={blockedLine} />
      </Group>
      <SkiaImage
        image={image}
        x={x}
        y={y}
        width={item.renderSize.width * scale}
        height={item.renderSize.height * scale}
        fit="contain"
        sampling={SPRITE_SAMPLING}
        opacity={spriteOpacity}
      />
      <Group transform={ringTransform} opacity={spriteOpacity}>
        <PenaltySprite geometry={placed.penalty ? { ...placed.penalty, rect: { ...placed.penalty.rect,
          x: placed.penalty.rect.x - placed.anchor.x, y: placed.penalty.rect.y - placed.anchor.y } } : null}
          scale={scale} images={images} />
        <StickerSprite geometry={placed.sticker ? { ...placed.sticker, rect: { ...placed.sticker.rect,
          x: placed.sticker.rect.x - placed.anchor.x, y: placed.sticker.rect.y - placed.anchor.y } } : null}
          scale={scale} image={images.get(SEIZURE_STICKER)} />
      </Group>
    </>
  );
}

type CoachCatSpriteProps = { scale: number; image: SkImage | undefined };

/**
 * 코치 고양이(AI 챗봇). 정지 이미지 한 장을 제자리 둘레로 둥둥 띄우고 조금씩 오가게 그린다(useCoachCatMotion).
 * 탭 영역은 홈이 씬 레이어에 따로 얹고 같은 훅으로 같이 움직인다(CoachTarget).
 */
function CoachCatSprite({ scale, image }: CoachCatSpriteProps) {
  const rect = React.useMemo(() => sceneRectToCanvas(COACH_CAT_RECT, scale), [scale]);
  const offset = useCoachCatMotion();
  const left = useDerivedValue(() => rect.x + offset.value.x * scale);
  const top = useDerivedValue(() => rect.y + offset.value.y * scale);
  if (!image) return null;
  return <SkiaImage image={image} x={left} y={top} width={rect.width} height={rect.height} fit="contain" sampling={SPRITE_SAMPLING} />;
}

type CharacterSpriteProps = { walker: CharacterWalker; scale: number; image: SkImage | undefined };

/**
 * 정지 이미지 한 장으로 움직이는 느낌을 낸다.
 * - 이동 중: 잔걸음 바운스(발끝 y 를 살짝 들었다 놓음), 진행 방향으로 미러링
 * - 정지 중: 호흡(발끝을 고정한 채 세로로 아주 조금 늘었다 줄어듦)
 */
function CharacterSprite({ walker, scale, image }: CharacterSpriteProps) {
  const { x, y, facing, moving, bobPhase, breathPhase } = walker;

  const rect = useDerivedValue(() => {
    const bob = moving.value ? Math.sin(bobPhase.value * Math.PI) * CHARACTER_MOTION.bob.height : 0;
    const breath = moving.value ? 0 : (breathPhase.value - 0.5) * 2 * CHARACTER_MOTION.breath.amount;
    const size = { width: CHARACTER_SIZE.width * (1 - breath * 0.5), height: CHARACTER_SIZE.height * (1 + breath) };
    return sceneRectToCanvas(getSpriteRect({ x: x.value, y: y.value - bob }, size), scale);
  });
  const left = useDerivedValue(() => rect.value.x);
  const top = useDerivedValue(() => rect.value.y);
  const spriteWidth = useDerivedValue(() => rect.value.width);
  const spriteHeight = useDerivedValue(() => rect.value.height);
  const flip = useDerivedValue(() => [{ scaleX: facing.value }]);
  const origin = useDerivedValue(() => ({ x: x.value * scale, y: 0 }));

  if (!image) return null;
  return (
    <Group transform={flip} origin={origin}>
      <SkiaImage image={image} x={left} y={top} width={spriteWidth} height={spriteHeight} fit="contain" sampling={SPRITE_SAMPLING} />
    </Group>
  );
}

export default RoomScene;
export { RoomScene };
export type { RoomSceneProps };
