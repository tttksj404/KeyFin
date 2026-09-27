import { useQueryClient } from "@tanstack/react-query";
import { useFocusEffect } from "expo-router";
import * as React from "react";

import { budgetKeys } from "@/features/budget/api/queries";
import { roomKeys } from "@/features/room/api/queries";

/** 푸시를 놓쳤어도 홈에 돌아오면 예산과 방을 새로 받는다. 진행 중인 조회는 함께 사용한다. */
export function useHomeDataRefresh(): void {
  const queryClient = useQueryClient();

  useFocusEffect(
    React.useCallback(() => {
      for (const queryKey of [budgetKeys.current(), roomKeys.home()]) {
        void queryClient.refetchQueries({ queryKey, exact: true, type: "active" }, { cancelRefetch: false });
      }
    }, [queryClient])
  );
}
