import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getFurnitures, updateFurniturePlacements, type FurnitureSlotType } from "@/features/room/api/furniture.api";
import { getUserItems, updateItemEquipment } from "@/features/room/api/item.api";
import { checkAttendance, getRoom, removeSticker } from "@/features/room/api/room.api";
import { placedFurnitureDtos, type UserFurniture } from "@/features/room/furniture";
import { applyAvatarEquipment, type UserItem } from "@/features/room/items";
import type { Room } from "@/features/room/model";
import { shopKeys } from "@/features/shop/api/queries";

export const roomKeys = {
  all: ["room"] as const,
  home: () => [...roomKeys.all, "home"] as const,
  /** 보유 가구. 배치를 저장하면 전체 성공 응답으로 교체한다 */
  furnitures: (slotType?: FurnitureSlotType) => [...roomKeys.all, "furnitures", slotType ?? "all"] as const,
  /** 보유 아바타 아이템(옷장). 갈아입으면 방 홈의 착장도 함께 무효화한다 */
  items: () => [...roomKeys.all, "items"] as const,
};

export function roomQueryOptions() {
  return queryOptions({
    queryKey: roomKeys.home(),
    queryFn: ({ signal }) => getRoom(signal),
    staleTime: 30_000,
    refetchOnWindowFocus: "always",
  });
}

export function useRoom() {
  return useQuery(roomQueryOptions());
}

/**
 * 출석 결과의 잔액을 방 캐시에 바로 반영한다 (docs/api-guide.md §5). 방은 재조회하지 않는다 — 서버 잔액이 응답에 있다.
 * 코인이 실제로 지급됐으면 새 이력이 생겼으니 코인 잔액·이력(PAGE-30)은 다시 받는다.
 */
export function useCheckAttendance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => checkAttendance(),
    onSuccess: (attendance) => {
      queryClient.setQueryData<Room>(roomKeys.home(), (old) =>
        old ? { ...old, coinBalance: attendance.balance, checkedInToday: true } : old
      );
      if (attendance.granted > 0) void queryClient.invalidateQueries({ queryKey: shopKeys.coins() });
    },
  });
}

export function furnitureListQueryOptions(slotType?: FurnitureSlotType) {
  return queryOptions({
    queryKey: roomKeys.furnitures(slotType),
    queryFn: ({ signal }) => getFurnitures(slotType, signal),
    staleTime: 30_000,
  });
}

/** 보유 가구 목록. 방 화면은 GET /room 의 furnitures 로 충분하고, 이 조회는 미설치 가구까지 볼 때 쓴다 */
export function useFurnitures(slotType?: FurnitureSlotType, enabled = true) {
  return useQuery({ ...furnitureListQueryOptions(slotType), enabled });
}

/** PUT 성공 응답을 먼저 반영한다. 조회 실패가 이미 성공한 저장을 실패로 바꾸지 않게 한다. */
export function useSavePlacements() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateFurniturePlacements,
    retry: false,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: roomKeys.all });
    },
    onSuccess: async (owned) => {
      await queryClient.cancelQueries({ queryKey: roomKeys.all });
      queryClient.setQueryData(roomKeys.furnitures(), owned);
      for (const slot of ["FLOOR", "WALL"] as const) {
        queryClient.setQueryData(roomKeys.furnitures(slot), owned.filter((item) => item.serverState.slotType === slot));
      }
      const installed = owned.filter((item) => item.serverState.placementStatus === "FLOOR");
      const count = installed.filter((item) => item.stickerAttached).length;
      queryClient.setQueryData<Room>(roomKeys.home(), (old) => old ? {
        ...old, furnitures: placedFurnitureDtos(owned),
        stickers: { count, total: installed.length, removableToday: count > 0 },
      } : old);
      await queryClient.invalidateQueries({ queryKey: roomKeys.home(), refetchType: "none" });
      await queryClient.fetchQuery(roomQueryOptions()).catch(() => undefined);
    },
  });
}

export function useRemoveSticker() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: removeSticker,
    retry: false,
    onMutate: () => queryClient.cancelQueries({ queryKey: roomKeys.all }),
    onSuccess: async (result) => {
      await queryClient.cancelQueries({ queryKey: roomKeys.all });
      queryClient.setQueryData<Room>(roomKeys.home(), (old) => old ? {
        ...old, stickers: result.stickers,
        furnitures: old.furnitures.map((item) => item.userFurnitureId === result.userFurnitureId
          ? { ...item, stickerAttached: result.stickerAttached } : item),
      } : old);
      queryClient.setQueriesData<UserFurniture[]>({ queryKey: [...roomKeys.all, "furnitures"] }, (old) => old?.map((item) =>
        item.userFurnitureId === result.userFurnitureId ? { ...item, stickerAttached: result.stickerAttached,
          serverState: { ...item.serverState, stickerAttached: result.stickerAttached } } : item));
      void queryClient.invalidateQueries({ queryKey: roomKeys.all });
    },
    // 다른 기기에서 제거했거나 이동한 경우도 최신 상태를 다시 받는다. 실패를 성공으로 표시하지 않는다.
    onError: () => { void queryClient.invalidateQueries({ queryKey: roomKeys.all }); },
  });
}

export function userItemsQueryOptions() {
  return queryOptions({
    queryKey: roomKeys.items(),
    queryFn: ({ signal }) => getUserItems(undefined, signal),
    staleTime: 30_000,
  });
}

/** 옷장의 보유 아이템. 부위가 6종뿐이라 한 번에 받아 화면에서 탭으로 나눈다 */
export function useUserItems() {
  return useQuery(userItemsQueryOptions());
}

type EquipmentChange = { userItemId: number; equipped: boolean };

/**
 * 아바타 한 벌을 입거나 벗는다 (FR-GAM-05). 서버가 같은 부위의 기존 아이템을 자동으로 벗기고 전체 착장을 돌려주므로,
 * 그 응답으로 목록의 착용 여부를 다시 맞춘다 — 바뀐 것만 고치면 자동으로 벗겨진 아이템이 입은 채로 남는다.
 * 방 캐릭터도 이 착장을 그리므로 방 홈을 다시 받는다.
 */
export function useUpdateItemEquipment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userItemId, equipped }: EquipmentChange) => updateItemEquipment(userItemId, { equipped }),
    onSuccess: (equipment) => {
      queryClient.setQueryData<UserItem[]>(roomKeys.items(), (old) => (old ? applyAvatarEquipment(old, equipment) : old));
      void queryClient.invalidateQueries({ queryKey: roomKeys.home() });
    },
  });
}
