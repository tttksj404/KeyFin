import { notifyManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react-native";
import { PortalHost } from "@rn-primitives/portal";
import * as React from "react";

import { ApiError } from "@/api/error";
import { applyBudgetStickersMock, furnitureListMock, placedFurnitureMock, removeStickerMock, resetFurnitureMocks, stickerStatusMock } from "@/api/mocks/furniture";
import { roomMock } from "@/api/mocks/room";
import { roomKeys, useRoom, useSavePlacements } from "@/features/room/api/queries";
import * as roomApi from "@/features/room/api/room.api";
import * as furnitureApi from "@/features/room/api/furniture.api";
import { RoomStickerTargets, StickerRemovalDialog } from "@/features/room/components/RoomStickers";
import { toPlacements, toUserFurnitures, type UserFurniture } from "@/features/room/furniture";
import { toRoom, type Room, type StickerRemoval } from "@/features/room/model";
import { buildPlacementsRequest } from "@/features/room/placements";
import type { Placement } from "@/features/room/scene";

notifyManager.setScheduler((callback) => callback());
let client: QueryClient;
const onClose = jest.fn();
beforeEach(() => {
  resetFurnitureMocks();
  applyBudgetStickersMock("202609");
  onClose.mockReset();
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } } });
  client.setQueryData(roomKeys.home(), toRoom({ ...roomMock, furnitures: placedFurnitureMock(), stickers: { count: 4, total: 4, removableToday: true }, overEnvelopes: [1, 4] }));
  client.setQueryData(roomKeys.furnitures(), toUserFurnitures(furnitureListMock()));
  client.setQueryData(roomKeys.furnitures("FLOOR"), toUserFurnitures(furnitureListMock("FLOOR")));
});
afterEach(() => { client.clear(); jest.restoreAllMocks(); });

async function dialog(count = 4) {
  return render(<QueryClientProvider client={client}>
    <StickerRemovalDialog placement={toPlacements(placedFurnitureMock())[0]} stickers={{ count, total: 4, removableToday: count > 0 }} onClose={onClose} />
    <PortalHost />
  </QueryClientProvider>);
}

it("딱지를 누르면 해당 보유 가구를 선택한다", async () => {
  const select = jest.fn();
  await render(<RoomStickerTargets width={327} placements={toPlacements(placedFurnitureMock())} furnitures={placedFurnitureMock()} onSelect={select} />);
  await fireEvent.press(screen.getByRole("button", { name: "소파 압류 딱지" }));
  expect(select).toHaveBeenCalledWith(expect.objectContaining({ itemId: "sofa_default", userFurnitureId: placedFurnitureMock().find((item) => item.assetKey === "sofa_default")!.userFurnitureId }));
});

it("제거 중 중복 클릭을 막고 성공 응답으로 홈과 보유 목록 캐시를 갱신한다", async () => {
  let resolve!: (value: StickerRemoval) => void;
  const remove = jest.spyOn(roomApi, "removeSticker").mockImplementation(() => new Promise((done) => { resolve = done; }));
  const target = placedFurnitureMock()[0].userFurnitureId;
  await dialog();
  const button = screen.getByRole("button", { name: "딱지 제거" });
  await fireEvent.press(button);
  await fireEvent.press(button);
  expect(remove).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "제거 중…" })).toBeDisabled();
  await act(async () => resolve({ userFurnitureId: target, stickerAttached: false, stickers: { count: 3, total: 4, removableToday: true } }));
  await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  const room = client.getQueryData<Room>(roomKeys.home())!;
  expect(room.stickers).toEqual({ count: 3, total: 4, removableToday: true });
  expect(room.overEnvelopeIds).toEqual([1, 4]);
  expect(room.furnitures.find((item) => item.userFurnitureId === target)?.stickerAttached).toBe(false);
  for (const key of [roomKeys.furnitures(), roomKeys.furnitures("FLOOR")]) {
    const owned = client.getQueryData<UserFurniture[]>(key)!;
    expect(owned.find((item) => item.userFurnitureId === target)).toMatchObject({ stickerAttached: false, serverState: { stickerAttached: false } });
  }
});

it("실패 시 딱지를 유지하고 같은 확인창에서 재시도할 수 있다", async () => {
  const target = placedFurnitureMock()[0].userFurnitureId;
  const remove = jest.spyOn(roomApi, "removeSticker")
    .mockRejectedValueOnce(new ApiError(0, "NETWORK", "offline"))
    .mockResolvedValueOnce({ userFurnitureId: target, stickerAttached: false, stickers: { count: 3, total: 4, removableToday: true } });
  await dialog();
  await fireEvent.press(screen.getByRole("button", { name: "딱지 제거" }));
  await waitFor(() => expect(screen.getByText("연결 상태를 확인한 뒤 다시 시도해 주세요.")).toBeTruthy());
  expect(onClose).not.toHaveBeenCalled();
  expect(client.getQueryData<Room>(roomKeys.home())?.stickers?.count).toBe(4);
  expect(screen.getByRole("button", { name: "딱지 제거" })).toBeEnabled();
  await fireEvent.press(screen.getByRole("button", { name: "딱지 제거" }));
  await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  expect(remove).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("alert")).toBeNull();
  expect(client.getQueryData<Room>(roomKeys.home())?.stickers).toEqual({ count: 3, total: 4, removableToday: true });
});

it("남은 딱지가 없으면 제거 버튼을 비활성화한다", async () => {
  const remove = jest.spyOn(roomApi, "removeSticker");
  await dialog(0);
  expect(screen.getByRole("button", { name: "딱지 제거" })).toBeDisabled();
  expect(screen.getByText("설치된 가구에 남은 딱지가 없어요.")).toBeTruthy();
  expect(remove).not.toHaveBeenCalled();
});

it("홈에서 다른 딱지를 연속 선택해 마지막 딱지까지 제거할 수 있다", async () => {
  jest.spyOn(roomApi, "getRoom").mockImplementation(async () => toRoom({
    ...roomMock, furnitures: placedFurnitureMock(), stickers: stickerStatusMock(),
  }));
  const remove = jest.spyOn(roomApi, "removeSticker").mockImplementation(async (id) => removeStickerMock(id));
  function HomeStickers() {
    const room = useRoom().data!;
    const [selected, select] = React.useState<Placement | null>(null);
    return <>
      <RoomStickerTargets width={327} placements={toPlacements(room.furnitures)} furnitures={room.furnitures} onSelect={select} />
      {selected ? <StickerRemovalDialog placement={selected} stickers={room.stickers} onClose={() => select(null)} /> : null}
      <PortalHost />
    </>;
  }
  await render(<QueryClientProvider client={client}><HomeStickers /></QueryClientProvider>);
  for (const [index, name] of ["소파", "TV", "식탁 (오리지널)", "커피 테이블 (오리지널)"].entries()) {
    await fireEvent.press(screen.getByRole("button", { name: `${name} 압류 딱지` }));
    expect(screen.getByRole("button", { name: "딱지 제거" })).toBeEnabled();
    expect(screen.queryByText(/하루|내일/)).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "딱지 제거" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "딱지 제거" })).toBeNull());
    expect(client.getQueryData<Room>(roomKeys.home())?.stickers).toEqual({ count: 3 - index, total: 4, removableToday: index < 3 });
  }
  expect(remove).toHaveBeenCalledTimes(4);
  expect(screen.queryAllByRole("button", { name: /압류 딱지$/ })).toHaveLength(0);
  await waitFor(() => expect(client.isFetching()).toBe(0));
});

it.each([true, false])("배치 저장 후 재조회가 실패해도 설치 상태(%s)에 맞게 제거 가능 여부를 갱신한다", async (installed) => {
  const snapshot = furnitureListMock().map((item) => ({ ...item, stickerAttached: false }));
  const bed = snapshot.find((item) => item.assetKey === "bed_pink")!;
  const response = toUserFurnitures(snapshot.map((item) => item === bed ? {
    ...item, stickerAttached: true, placed: installed, placementStatus: installed ? "FLOOR" : null,
    placementDirection: installed ? "FRONT_RIGHT" : null, positionX: installed ? 100 : null, positionY: installed ? 500 : null,
  } : item));
  jest.spyOn(furnitureApi, "updateFurniturePlacements").mockResolvedValue(response);
  jest.spyOn(roomApi, "getRoom").mockRejectedValue(new Error("offline"));
  client.setQueryData<Room>(roomKeys.home(), (old) => ({ ...old!, stickers: { count: installed ? 0 : 1, total: 4, removableToday: !installed } }));
  const hook = await renderHook(() => useSavePlacements(), {
    wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  const request = buildPlacementsRequest(toPlacements(placedFurnitureMock()), toUserFurnitures(snapshot));
  await act(async () => { await hook.result.current.mutateAsync(request); });
  expect(client.getQueryData<Room>(roomKeys.home())?.stickers).toEqual({
    count: installed ? 1 : 0, total: installed ? 5 : 4, removableToday: installed,
  });
});
