import { api } from "@/api/client";
import * as client from "@/api/client";
import { ApiError } from "@/api/error";
import { acquireFurnitureMock, applyBudgetStickersMock, furnitureListMock, placedFurnitureMock, removeStickerMock,
  resetFurnitureMocks, stickerStatusMock, updateFurniturePlacementsMock } from "@/api/mocks/furniture";
import { removeSticker } from "@/features/room/api/room.api";
import { FURNITURE, type FurnitureId } from "@/features/room/catalog";
import { toPlacements, toUserFurnitures } from "@/features/room/furniture";
import { buildPlacementsRequest } from "@/features/room/placements";
import { stickerErrorMessage, stickerGeometry, stickerPlacements } from "@/features/room/stickers";

const currentRequest = () => buildPlacementsRequest(toPlacements(placedFurnitureMock()), toUserFurnitures(furnitureListMock()));
const ordinary = (id: number, asset = "refrigerator_black") => {
  acquireFurnitureMock(id, id, asset);
  return { ...currentRequest().placements[0], userFurnitureId: id };
};
beforeEach(() => resetFurnitureMocks());
afterEach(() => jest.restoreAllMocks());

it("최초 초과 때 설치된 바닥 가구만 부착하고 이후 설치는 다음 기간까지 제외한다", () => {
  const fridge = ordinary(900);
  const rug = ordinary(901, "decor_checker_rug");
  const wall = { ...ordinary(902, "decor_round_wall_clock"), placementStatus: "LEFT_WALL" as const };
  const later = ordinary(903, "bed_black");
  updateFurniturePlacementsMock({ placements: [...currentRequest().placements, fridge, rug, wall] });
  applyBudgetStickersMock("202609");
  expect(stickerStatusMock()).toEqual({ count: 6, total: 6, removableToday: true });
  expect(furnitureListMock().filter((item) => [902, 903].includes(item.userFurnitureId)).every((item) => !item.stickerAttached)).toBe(true);
  updateFurniturePlacementsMock({ placements: [...currentRequest().placements, later] });
  applyBudgetStickersMock("202609");
  expect(stickerStatusMock().count).toBe(6);
  expect(stickerStatusMock().total).toBe(7);
  applyBudgetStickersMock("202610");
  expect(stickerStatusMock().count).toBe(7);
});

it("일반 가구 보관·재설치·이동은 딱지를 유지하고 제거한 딱지는 다시 생기지 않는다", () => {
  const initial = currentRequest();
  const fridge = ordinary(900);
  const full = { placements: [...initial.placements, fridge] };
  updateFurniturePlacementsMock(full);
  applyBudgetStickersMock("202609");
  updateFurniturePlacementsMock(initial);
  expect(furnitureListMock().find((item) => item.userFurnitureId === 900)).toMatchObject({ placed: false, stickerAttached: true });
  expect(stickerStatusMock().count).toBe(4);
  expect(() => removeStickerMock(900)).toThrow(expect.objectContaining({ code: "ROOM_001" }));
  updateFurniturePlacementsMock(full);
  expect(stickerStatusMock().count).toBe(5);
  removeStickerMock(900);
  updateFurniturePlacementsMock(initial);
  updateFurniturePlacementsMock(full);
  applyBudgetStickersMock("202609");
  expect(stickerStatusMock()).toMatchObject({ count: 4, total: 5, removableToday: true });
});

it("날짜를 기다리지 않고 모든 딱지를 제거하고 같은 딱지의 중복 제거는 거절한다", () => {
  applyBudgetStickersMock("202609");
  const installed = placedFurnitureMock();
  installed.forEach((item, index) => {
    const remaining = installed.length - index - 1;
    expect(removeStickerMock(item.userFurnitureId).stickers).toEqual({ count: remaining, total: installed.length, removableToday: remaining > 0 });
    expect(() => removeStickerMock(item.userFurnitureId)).toThrow(expect.objectContaining({ code: "ROOM_003" }));
  });
  applyBudgetStickersMock("202609");
  expect(stickerStatusMock()).toEqual({ count: 0, total: 4, removableToday: false });
  applyBudgetStickersMock("202610");
  expect(removeStickerMock(installed[0].userFurnitureId).stickers).toEqual({ count: 3, total: 4, removableToday: true });
});

it("스타일 교체 미리보기와 저장 결과는 새 필수 가구에만 딱지를 표시한다", () => {
  applyBudgetStickersMock("202609");
  acquireFurnitureMock(900, 900, "sofa_black");
  const owned = furnitureListMock();
  const oldSofa = owned.find((item) => item.furnitureType === "SOFA" && item.placed)!;
  const draft = toPlacements(placedFurnitureMock()).map((p) => p.userFurnitureId === oldSofa.userFurnitureId
    ? { ...p, itemId: "sofa_black" as const, userFurnitureId: 900 } : p);
  expect(stickerPlacements(draft, owned, true).map((p) => p.userFurnitureId)).toContain(900);
  updateFurniturePlacementsMock(buildPlacementsRequest(draft, toUserFurnitures(owned)));
  expect(furnitureListMock().find((item) => item.userFurnitureId === oldSofa.userFurnitureId)?.stickerAttached).toBe(false);
  removeStickerMock(900);
  expect(stickerPlacements(draft, furnitureListMock(), true)).toHaveLength(3);
});

it.each(Object.keys(FURNITURE) as FurnitureId[])("%s의 양방향 바닥 딱지 위치가 있고 벽 가구는 제외된다", (itemId) => {
  const item = FURNITURE[itemId];
  for (const direction of ["FRONT_RIGHT", "FRONT_LEFT"] as const) {
    const placement = { itemId, anchor: { x: 160, y: 400 }, direction };
    const geometry = stickerGeometry(placement);
    if (item.slot === "WALL") expect(geometry).toBeNull();
    else {
      expect(geometry).not.toBeNull();
      expect(geometry!.rect.width).toBeGreaterThan(0);
      expect(geometry!.rect.height / geometry!.rect.width).toBeCloseTo(256 / 480);
      const moved = stickerGeometry({ ...placement, anchor: { x: 190, y: 410 } })!;
      expect(moved.rect.x - geometry!.rect.x).toBeCloseTo(30);
      expect(moved.rect.y - geometry!.rect.y).toBeCloseTo(10);
    }
  }
});

it("제거 API는 기존 경로와 보유 ID를 사용한다", async () => {
  jest.spyOn(client, "isMocked").mockReturnValue(false);
  const result = { userFurnitureId: 900, stickerAttached: false, stickers: { count: 5, total: 8, removableToday: true } };
  const post = jest.spyOn(api, "post").mockResolvedValue({ data: result });
  expect(await removeSticker(900)).toEqual(result);
  expect(post).toHaveBeenCalledWith("/room/stickers/removals", { userFurnitureId: 900 });
});

it("제거 실패 원인에 맞는 안내를 보여 준다", () => {
  expect(stickerErrorMessage(new ApiError(409, "ROOM_003", "error"))).toContain("이미 제거");
  expect(stickerErrorMessage(new ApiError(0, "NETWORK", "error"))).toContain("연결");
});
