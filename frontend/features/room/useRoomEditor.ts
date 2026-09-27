import { useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { furnitureListQueryOptions, roomQueryOptions, useSavePlacements } from "@/features/room/api/queries";
import { placedFurnitureDtos, toPlacements, type UserFurniture } from "@/features/room/furniture";
import { buildPlacementsRequest, placementErrorMessage } from "@/features/room/placements";
import { useRoomStore } from "@/features/room/store";

/** 원본 보유 목록은 편집 시작 시 고정하고, 성공한 PUT 응답만 확정본으로 반영한다. */
export function useRoomEditor() {
  const client = useQueryClient();
  const save = useSavePlacements();
  const [owned, setOwned] = React.useState<readonly UserFurniture[] | null>(null);
  const [loadError, setLoadError] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [attempt, setAttempt] = React.useState(0);
  const [completed, setCompleted] = React.useState(false);
  const mounted = React.useRef(false);
  const saving = useRoomStore((state) => state.saving);
  const draft = useRoomStore((state) => state.draft);

  React.useEffect(() => { setError(null); }, [draft]);

  React.useEffect(() => {
    let active = true;
    mounted.current = true;
    setLoadError(false);
    const initialize = async () => {
      // /room의 기본 지급이 끝난 뒤 목록을 조회해야 최초 진입도 같은 기준으로 편집한다.
      await client.fetchQuery({ ...roomQueryOptions(), staleTime: 0 });
      if (!active) return;
      // 방 조회 전에 다른 화면에서 시작한 목록 요청을 공유하지 않는다.
      await client.cancelQueries({ queryKey: furnitureListQueryOptions().queryKey, exact: true });
      const snapshot = await client.fetchQuery({ ...furnitureListQueryOptions(), staleTime: 0 });
      if (!active) return;
      useRoomStore.getState().startEdit(toPlacements(placedFurnitureDtos(snapshot)));
      setOwned(snapshot);
    };
    void initialize().catch(() => { if (active) setLoadError(true); });
    return () => {
      active = false;
      mounted.current = false;
      useRoomStore.getState().setSaving(false);
      useRoomStore.getState().cancelEdit();
    };
  }, [client, attempt]);

  const submit = async () => {
    const state = useRoomStore.getState();
    if (owned === null || !state.draft || state.saving || completed) return;
    setError(null);
    try {
      const request = buildPlacementsRequest(state.draft, owned);
      state.setSaving(true); // 재렌더 전에 연속 클릭과 드래그부터 막는다.
      const response = await save.mutateAsync(request);
      if (!mounted.current) return;
      useRoomStore.getState().commitEdit(toPlacements(placedFurnitureDtos(response)));
      setCompleted(true);
    } catch (cause) {
      if (mounted.current) setError(placementErrorMessage(cause));
    } finally {
      if (mounted.current) useRoomStore.getState().setSaving(false);
    }
  };

  return { owned, saving, completed, error, loadError, ready: owned !== null,
    retry: () => setAttempt((value) => value + 1), submit };
}
