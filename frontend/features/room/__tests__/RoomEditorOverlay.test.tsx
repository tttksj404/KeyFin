import { notifyManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import * as React from "react";

import { acquireFurnitureMock, applyBudgetStickersMock, furnitureListMock, resetFurnitureMocks } from "@/api/mocks/furniture";
import { ApiError } from "@/api/error";
import * as furnitureApi from "@/features/room/api/furniture.api";
import * as roomApi from "@/features/room/api/room.api";
import { roomKeys } from "@/features/room/api/queries";
import { toUserFurnitures, type UserFurniture } from "@/features/room/furniture";
import { EDIT_LABEL, ROOM_EDIT_ROUTE, RoomEditorOverlay } from "@/features/room/components/RoomEditorOverlay";
import { EDIT_HINT, EDIT_ROOM_AREA_TEST_ID, RoomEditScreen, STORAGE_TITLE } from "@/features/room/components/RoomEditScreen";
import { FURNITURE, WALL_ITEMS } from "@/features/room/catalog";
import { cellAnchor } from "@/features/room/grid";
import { DEFAULT_LAYOUT, SURFACES } from "@/features/room/scene";
import { useRoomStore } from "@/features/room/store";
import type { Room } from "@/features/room/model";

// 목 응답이 act 범위 안에서 반영되도록 쿼리 알림을 그 자리에서 보낸다(HomeScreen 테스트와 같은 설정).
notifyManager.setScheduler((callback) => callback());

const mockPush = jest.fn();
const mockBack = jest.fn();
const mockPreventRemove = jest.fn();
jest.mock("expo-router/react-navigation", () => ({ usePreventRemove: (...args: unknown[]) => mockPreventRemove(...args) }));
jest.mock("@/api/mocks/latency", () => ({ withMockLatency: async <T,>(value: T) => value }));
jest.mock("expo-router", () => {
  const ReactActual = jest.requireActual<typeof import("react")>("react");
  return {
    useRouter: () => ({ push: mockPush, back: mockBack, replace: jest.fn(), canGoBack: () => true }),
    useFocusEffect: (effect: () => void) => ReactActual.useEffect(effect, [effect]),
  };
});

/** 소파를 옮겨 놓는 자리. 드래그는 칸에만 놓이므로 실제 칸의 기준점을 쓴다 (111.625, 538) */
const SOFA_MOVED = cellAnchor(SURFACES.FLOOR, { col: 8, row: 10 }, FURNITURE.sofa_default.grid);
const BOARD_MOVED = cellAnchor(SURFACES.WALL_RIGHT, { col: 4, row: 4 }, WALL_ITEMS.board.grid);

const sofaAnchor = () => useRoomStore.getState().layout.find((p) => p.itemId === "sofa_default")!.anchor;

/** 편집 화면은 GET /room 으로 서버 배치를 받고 나서 사본을 뜬다. 목이 기본 배치를 그대로 주므로 자리는 같다 */
async function renderEditScreen(props: { openStorage?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { gcTime: 0 } } });
  return { client, view: await render(
    <QueryClientProvider client={client}>
      <RoomEditScreen {...props} />
    </QueryClientProvider>
  ) };
}

async function renderEditing(props: { openStorage?: boolean } = {}) {
  const { view } = await renderEditScreen(props);
  await waitFor(() => expect(useRoomStore.getState().draft).not.toBeNull());
  await waitFor(() => expect(screen.getByRole("button", { name: "편집 완료" })).toBeEnabled());
  await layoutRoomArea();
  return view;
}

/** 말풍선은 방 크기를 잰 뒤에만 뜬다. 테스트에는 실제 레이아웃이 없어 크기를 흘려 넣는다 */
async function layoutRoomArea() {
  await fireEvent(screen.getByTestId(EDIT_ROOM_AREA_TEST_ID), "layout", { nativeEvent: { layout: { width: 327, height: 586 } } });
}

describe("방 꾸미기 진입과 편집 화면", () => {
  beforeEach(() => {
    useRoomStore.setState({ layout: DEFAULT_LAYOUT, draft: null, selectedId: null, saving: false });
    resetFurnitureMocks();
    mockPush.mockReset();
    mockBack.mockReset();
    mockPreventRemove.mockReset();
  });
  afterEach(() => jest.restoreAllMocks());

  it("홈의 꾸미기 버튼은 편집 화면으로 간다", async () => {
    await render(<RoomEditorOverlay />);
    await fireEvent.press(screen.getByRole("button", { name: EDIT_LABEL }));
    expect(mockPush).toHaveBeenCalledWith(ROOM_EDIT_ROUTE);
    expect(useRoomStore.getState().draft).toBeNull();
  });

  it("딱지가 붙은 일반 가구를 보관하면 부착 표시와 재설치 안내가 보인다", async () => {
    const list = furnitureListMock();
    const bed = list.find((item) => item.assetKey === "bed_pink")!;
    resetFurnitureMocks(list.map((item) => item.userFurnitureId === bed.userFurnitureId ? {
      ...item, placed: true, placementStatus: "FLOOR", placementDirection: "FRONT_RIGHT", positionX: 100, positionY: 500,
    } : item));
    applyBudgetStickersMock("202609");
    await renderEditing();
    await act(() => useRoomStore.getState().removeItem("bed_pink"));
    await fireEvent.press(screen.getByRole("button", { name: /^보관함 열기/ }));
    expect(await screen.findByRole("button", { name: `${bed.name}, 압류 딱지 부착, 방에 놓기` })).toBeTruthy();
    expect(screen.getByText("압류 딱지는 다시 설치한 뒤 제거할 수 있어요.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "딱지 제거" })).toBeNull();
  });

  it("편집 화면에 들어오면 사본을 만들고, 취소는 옮긴 것을 버리고 돌아간다", async () => {
    await renderEditing();
    expect(screen.getByText(EDIT_HINT)).toBeTruthy();

    await act(() => useRoomStore.getState().moveItem("sofa_default", SOFA_MOVED));
    // 취소는 헤더의 뒤로가기다(2026-09-21 — 방을 크게 쓰려고 하단 취소/완료 줄을 없앴다)
    expect(screen.queryByRole("button", { name: "편집 취소" })).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "뒤로" }));
    expect(sofaAnchor()).toEqual(DEFAULT_LAYOUT.find((p) => p.itemId === "sofa_default")!.anchor);
    expect(useRoomStore.getState().draft).toBeNull();
    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  it("완료는 옮긴 가구를 서버에 저장한 뒤 확정하고 돌아간다 — 벽 오브젝트도 같은 사본에서 옮긴다", async () => {
    await renderEditing();
    await act(() => {
      useRoomStore.getState().moveItem("sofa_default", SOFA_MOVED);
      useRoomStore.getState().moveItem("board", BOARD_MOVED);
    });
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));

    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1), { timeout: 3000 });
    expect(sofaAnchor()).toEqual(SOFA_MOVED);
    expect(useRoomStore.getState().layout.find((p) => p.itemId === "board")!.anchor).toEqual(BOARD_MOVED);
    expect(useRoomStore.getState().draft).toBeNull();
  });

  it("옮긴 자리는 서버 목에 남아 다시 들어와도 그대로다", async () => {
    const first = await renderEditing();
    await act(() => useRoomStore.getState().moveItem("sofa_default", SOFA_MOVED));
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1), { timeout: 3000 });
    await first.unmount();

    useRoomStore.setState({ layout: DEFAULT_LAYOUT, draft: null, selectedId: null });
    await renderEditing();
    await waitFor(() => expect(sofaAnchor()).toEqual(SOFA_MOVED), { timeout: 3000 });
  });

  it("보관함은 접혀 있다가 손잡이를 누르면 올라오고, 가구를 꺼내면 방에 놓이며 다시 내려간다", async () => {
    await renderEditing();
    const handle = await screen.findByRole("button", { name: /^보관함 열기, \d+개$/ });
    expect(screen.queryByRole("header", { name: STORAGE_TITLE })).toBeNull();

    await fireEvent.press(handle);
    expect(await screen.findByRole("header", { name: STORAGE_TITLE })).toBeTruthy();

    const before = useRoomStore.getState().draft?.length ?? 0;
    const tiles = await screen.findAllByRole("button", { name: /, 방에 놓기$/ });
    expect(tiles.length).toBeGreaterThan(1);
    await fireEvent.press(tiles[0]);
    expect(useRoomStore.getState().draft?.length).toBe(before + 1);
    await waitFor(() => expect(screen.queryByRole("header", { name: STORAGE_TITLE })).toBeNull());
  });

  it("상점에서 가구를 사고 넘어오면 보관함을 펴 둔 채로 연다", async () => {
    await renderEditing({ openStorage: true });
    expect(await screen.findByRole("header", { name: STORAGE_TITLE })).toBeTruthy();
  });

  it("가구를 고르면 그 옆에 동작 버튼이 뜨고, 벽 오브젝트는 옮기기만 할 수 있다고 알려 준다", async () => {
    await renderEditing();
    expect(screen.queryByRole("button", { name: /방향 바꾸기$/ })).toBeNull();

    await act(async () => useRoomStore.getState().select("sofa_default"));
    expect(await screen.findByRole("button", { name: /방향 바꾸기$/ })).toBeTruthy();
    // 필수 가구도 편집 중에는 넣어 둘 수 있다 — 개수는 완료할 때 검사한다
    expect(screen.getByRole("button", { name: /넣어 두기$/ }).props.accessibilityState).toMatchObject({ disabled: false });

    await act(async () => useRoomStore.getState().select("board"));
    expect(screen.getByRole("button", { name: /넣어 두기$/ }).props.accessibilityState).toMatchObject({ disabled: true });
    expect(screen.getByText("예산 보드·출금 캘린더는 옮기기만 할 수 있어요.")).toBeTruthy();
    // 가구를 고른 동안에는 사용법 안내를 치운다 — 방을 가리는 글을 하나라도 줄인다
    expect(screen.queryByText(EDIT_HINT)).toBeNull();
  });

  it("화면을 떠나면(언마운트) 남은 사본은 버린다", async () => {
    const view = await renderEditing();
    await act(() => useRoomStore.getState().moveItem("sofa_default", SOFA_MOVED));
    await view.unmount();
    expect(useRoomStore.getState().draft).toBeNull();
    expect(sofaAnchor()).toEqual(DEFAULT_LAYOUT.find((p) => p.itemId === "sofa_default")!.anchor);
  });

  it("변경이 없어도 완료는 최종 4종을 한 번에 보낸다", async () => {
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements");
    await renderEditing();
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1));
    expect(save).toHaveBeenCalledTimes(1);
    expect(save.mock.calls[0][0].placements).toHaveLength(4);
  });

  it("기본 소파를 보관하고 구매 소파를 꺼내 전체 배치를 저장한다", async () => {
    acquireFurnitureMock(18, 900, "sofa_black");
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements");
    await renderEditing();
    await act(() => useRoomStore.getState().select("sofa_default"));
    await fireEvent.press(screen.getByRole("button", { name: "소파 넣어 두기" }));
    expect(useRoomStore.getState().draft!.some((item) => item.itemId === "sofa_default")).toBe(false);
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    expect(await screen.findByText(/소파 0개/)).toBeTruthy();
    expect(save).not.toHaveBeenCalled();
    // 보관함은 접혀 있어 손잡이로 시트를 올린 뒤 꺼낸다(2026-09-21 배치)
    await fireEvent.press(await screen.findByRole("button", { name: /^보관함 열기/ }));
    await fireEvent.press(await screen.findByRole("button", { name: "2인 소파 (블랙), 방에 놓기" }));
    expect(screen.queryByText(/소파 0개/)).toBeNull();
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][0].placements.some((item) => item.userFurnitureId === 900)).toBe(true);
    expect(furnitureListMock().find((item) => item.assetKey === "sofa_default")?.placed).toBe(false);
    expect(useRoomStore.getState().layout.some((item) => item.itemId === "sofa_black")).toBe(true);
  });

  it("구매 소파를 추가한 중복 상태에서는 사본을 유지하고 저장하지 않는다", async () => {
    acquireFurnitureMock(18, 900, "sofa_black");
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements");
    await renderEditing();
    await act(() => useRoomStore.getState().placeItem({ itemId: "sofa_black", userFurnitureId: 900, anchor: SOFA_MOVED }));
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    expect(await screen.findByText(/소파 2개/)).toBeTruthy();
    expect(save).not.toHaveBeenCalled();
    expect(useRoomStore.getState().draft).not.toBeNull();
  });

  it("방 조회 이후 전체 목록을 기다리고 조회 실패는 재시도한다", async () => {
    const room = jest.spyOn(roomApi, "getRoom");
    const list = jest.spyOn(furnitureApi, "getFurnitures").mockRejectedValueOnce(new Error("offline"));
    await renderEditScreen();
    expect(screen.getByRole("button", { name: "편집 완료" })).toBeDisabled();
    expect(useRoomStore.getState().draft).toBeNull();
    await fireEvent.press(await screen.findByRole("button", { name: "다시 시도" }));
    await waitFor(() => expect(useRoomStore.getState().draft).not.toBeNull());
    expect(room.mock.invocationCallOrder[0]).toBeLessThan(list.mock.invocationCallOrder[0]);
    expect(list).toHaveBeenCalledTimes(2);
  });

  it("백그라운드 목록 갱신이 편집 기준이나 사본을 덮어쓰지 않는다", async () => {
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements");
    const { client } = await renderEditScreen();
    await waitFor(() => expect(useRoomStore.getState().draft).not.toBeNull());
    await waitFor(() => expect(screen.getByRole("button", { name: "편집 완료" })).toBeEnabled());
    await act(() => {
      useRoomStore.getState().moveItem("sofa_default", SOFA_MOVED);
      client.setQueryData(roomKeys.furnitures(), []);
      useRoomStore.getState().hydrate([]);
    });
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][0].placements).toHaveLength(4);
    expect(client.getQueryData<UserFurniture[]>(roomKeys.furnitures())).toHaveLength(8);
  });

  it("화면에 없는 설치 가구를 보존하고 응답 목록을 캐시에 반영한다", async () => {
    const hidden = {
      ...furnitureListMock()[0], userFurnitureId: 900, itemId: 900, assetKey: "future_furniture",
      furnitureType: null, defaultFurnitureType: null, canUnplace: true,
      placementDirection: "FRONT_LEFT", positionX: 123.123, positionY: 500.001, layer: -3,
    };
    resetFurnitureMocks([...furnitureListMock(), hidden]);
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements");
    const { client } = await renderEditScreen();
    await waitFor(() => expect(screen.getByRole("button", { name: "편집 완료" })).toBeEnabled());
    expect(useRoomStore.getState().draft!.some((item) => item.userFurnitureId === 900)).toBe(false);
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][0].placements).toContainEqual({
      userFurnitureId: 900, placementStatus: "FLOOR", placementDirection: "FRONT_LEFT",
      positionX: 123.123, positionY: 500.001, layer: -3,
    });
    expect(furnitureListMock().find((item) => item.userFurnitureId === 900)).toEqual(hidden);
    expect(client.getQueryData<UserFurniture[]>(roomKeys.furnitures())).toEqual(toUserFurnitures(furnitureListMock()));
    expect(client.getQueryData<Room>(roomKeys.home())!.furnitures).toHaveLength(5);
  });

  it("저장 후 방 재조회 실패에도 성공 응답과 로컬 보드 위치를 유지한다", async () => {
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements");
    const { client } = await renderEditScreen();
    await waitFor(() => expect(screen.getByRole("button", { name: "편집 완료" })).toBeEnabled());
    jest.spyOn(roomApi, "getRoom").mockRejectedValueOnce(new ApiError(0, "NETWORK", ""));
    await act(() => {
      useRoomStore.getState().moveItem("sofa_default", SOFA_MOVED);
      useRoomStore.getState().moveItem("board", BOARD_MOVED);
    });
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1));
    expect(save).toHaveBeenCalledTimes(1);
    expect(sofaAnchor()).toEqual(SOFA_MOVED);
    expect(useRoomStore.getState().layout.find((item) => item.itemId === "board")!.anchor).toEqual(BOARD_MOVED);
    expect(client.getQueryData<Room>(roomKeys.home())!.furnitures.find((item) => item.assetKey === "sofa_default"))
      .toMatchObject({ positionX: SOFA_MOVED.x, positionY: SOFA_MOVED.y });
    expect(useRoomStore.getState().draft).toBeNull();
  });

  it("저장 실패는 사본을 유지하고 재시도는 동일 전체 배치를 보낸다", async () => {
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements").mockRejectedValueOnce(new ApiError(0, "TIMEOUT", ""));
    await renderEditing();
    await act(() => useRoomStore.getState().moveItem("sofa_default", SOFA_MOVED));
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    expect(await screen.findByText(/연결 상태/)).toBeTruthy();
    expect(useRoomStore.getState().draft).not.toBeNull();
    expect(mockBack).not.toHaveBeenCalled();
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][0]).toEqual(save.mock.calls[1][0]);
  });

  it("저장 중에는 연속 완료·취소·뒤로·스토어의 배치 변경을 막는다", async () => {
    let finish!: (value: UserFurniture[]) => void;
    const save = jest.spyOn(furnitureApi, "updateFurniturePlacements").mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    await renderEditing();
    const before = useRoomStore.getState().draft;
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(mockPreventRemove).toHaveBeenLastCalledWith(true, expect.any(Function));
    await fireEvent.press(screen.getByRole("button", { name: "편집 완료" }));
    await fireEvent.press(screen.getByRole("button", { name: "뒤로" }));
    await act(() => {
      const state = useRoomStore.getState();
      state.moveItem("sofa_default", SOFA_MOVED);
      state.removeItem("sofa_default");
      state.flipItem("sofa_default");
      state.placeItem({ itemId: "sofa_black", anchor: SOFA_MOVED });
    });
    expect(useRoomStore.getState().draft).toBe(before);
    expect(save).toHaveBeenCalledTimes(1);
    expect(mockBack).not.toHaveBeenCalled();
    await act(async () => finish(toUserFurnitures(furnitureListMock())));
    await waitFor(() => expect(mockBack).toHaveBeenCalledTimes(1));
  });
});
