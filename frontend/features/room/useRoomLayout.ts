import * as React from "react";

import { useRoom } from "@/features/room/api/queries";
import { toPlacements } from "@/features/room/furniture";
import { useRoomStore } from "@/features/room/store";

/**
 * 서버가 준 배치(GET /room 의 furnitures)를 방 스토어에 맞춘다 (방 3단계).
 * 외부 저장소(zustand)와의 동기화라 effect 로 둔다. 편집 중이거나 설치된 가구가 없으면 스토어가 지금 배치를 지킨다 —
 * 아이템 시드가 들어오기 전 실서버는 빈 배열을 주므로 그때는 기본 배치가 그대로 보인다(사용자 결정 2026-09-16).
 */
export function useRoomLayoutSync(): void {
  const room = useRoom();
  const hydrate = useRoomStore((state) => state.hydrate);
  const furnitures = room.data?.furnitures;

  React.useEffect(() => {
    if (furnitures === undefined) return;
    hydrate(toPlacements(furnitures));
  }, [furnitures, hydrate]);
}
