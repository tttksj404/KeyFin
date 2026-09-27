import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useFocusEffect } from "expo-router";
import * as React from "react";

/**
 * 화면이 다시 앞에 올 때 그 화면이 보는 조회 중 오래된(stale) 것만 다시 받는다.
 * 탭 화면과 스택 아래에 깔린 화면은 계속 마운트돼 있어 refetchOnMount 가 돌지 않는다 — 새로 열리는 상세 화면은 최신인데
 * 돌아온 홈·목록은 옛 값인 채로 남는 원인이었다 (2026-09-22). staleTime 안쪽이면 아무 요청도 보내지 않는다.
 * queryKey 는 `roomKeys.all` 같은 모듈 상수를 넘긴다 — 렌더마다 새 배열이면 포커스 효과가 매번 다시 돈다.
 */
export function useRefetchStaleOnFocus(queryKey: QueryKey) {
  const queryClient = useQueryClient();

  useFocusEffect(
    React.useCallback(() => {
      // 막 마운트돼 이미 받고 있는 조회는 끊지 않는다
      void queryClient.refetchQueries({ queryKey, type: "active", stale: true }, { cancelRefetch: false });
    }, [queryClient, queryKey])
  );
}
