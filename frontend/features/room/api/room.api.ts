import { api, isMocked } from "@/api/client";
import { withMockLatency } from "@/api/mocks/latency";
import { placedFurnitureMock, removeStickerMock, stickerStatusMock } from "@/api/mocks/furniture";
import { attendanceMock, roomMock } from "@/api/mocks/room";
import { overEnvelopeIdsMock } from "@/api/mocks/budget";
import { toAttendance, toRoom, type Attendance, type AttendanceDto, type Room, type RoomDto, type StickerRemoval } from "@/features/room/model";

/** GET /room — 방 홈 화면 데이터: 착장·반응·설치 가구·코인·출석 상태 (docs/api-contract.md GAME, FR-GAM-01) */
export async function getRoom(signal?: AbortSignal): Promise<Room> {
  // 가구는 목도 서버처럼 상태를 들고 있어 방 꾸미기에서 옮긴 자리가 유지된다
  if (isMocked("room")) return toRoom(await withMockLatency({ ...roomMock, furnitures: placedFurnitureMock(), stickers: stickerStatusMock(), overEnvelopes: overEnvelopeIdsMock() }, signal));
  const { data } = await api.get<RoomDto>("/room", { signal });
  return toRoom(data);
}

/**
 * POST /fin-coins/attendance — 당일 첫 출석에 10코인 (FR-GAM-03, 2026-09-16 Swagger 대조로 경로 정정).
 * 날짜는 서버가 사용자 잠금을 잡고 KST 로 정한다. 당일 재요청도 200 이고 granted=0 · balance 는 최신 잔액이다.
 */
export async function checkAttendance(): Promise<Attendance> {
  if (isMocked("room")) return toAttendance(await withMockLatency(attendanceMock));
  const { data } = await api.post<AttendanceDto>("/fin-coins/attendance");
  return toAttendance(data);
}

export async function removeSticker(userFurnitureId: number): Promise<StickerRemoval> {
  if (isMocked("room")) return withMockLatency(removeStickerMock(userFurnitureId));
  const { data } = await api.post<StickerRemoval>("/room/stickers/removals", { userFurnitureId });
  return data;
}
