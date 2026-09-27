import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { selectAuthStatus, useAuthStore } from "@/features/auth/store";
import {
  getCoachPersona,
  getNotificationSettings,
  getTransferSettings,
  updateCoachPersona,
  updateNotificationSettings,
  updateTransferSettings,
} from "@/features/settings/api/settings.api";
import { toCoachPersonaRequest, type CoachPersona, type NotificationSettings, type TransferSettings } from "@/features/settings/model";

export const settingsKeys = {
  all: ["settings"] as const,
  transfer: () => [...settingsKeys.all, "transfer"] as const,
  notifications: () => [...settingsKeys.all, "notifications"] as const,
  coach: () => [...settingsKeys.all, "coach"] as const,
};

export function transferSettingsQueryOptions() {
  return queryOptions({
    queryKey: settingsKeys.transfer(),
    queryFn: ({ signal }) => getTransferSettings(signal),
    staleTime: 60_000,
  });
}

export function useTransferSettings() {
  const authStatus = useAuthStore(selectAuthStatus);
  return useQuery({ ...transferSettingsQueryOptions(), enabled: authStatus === "authenticated" });
}

/**
 * 저장 응답이 곧 새 설정이라 캐시에 바로 쓴다 (docs/api-guide.md §5).
 * 돈이 움직이는 설정이라 자동 재시도는 하지 않는다 — 실패는 화면이 문구와 재시도 수단으로 알린다 (규칙 80).
 */
export function useUpdateTransferSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateTransferSettings,
    retry: false,
    onSuccess: (settings) => queryClient.setQueryData<TransferSettings>(settingsKeys.transfer(), settings),
  });
}

export function notificationSettingsQueryOptions() {
  return queryOptions({
    queryKey: settingsKeys.notifications(),
    queryFn: ({ signal }) => getNotificationSettings(signal),
    staleTime: 60_000,
  });
}

export function useNotificationSettings() {
  const authStatus = useAuthStore(selectAuthStatus);
  return useQuery({ ...notificationSettingsQueryOptions(), enabled: authStatus === "authenticated" });
}

/**
 * 토글·시간을 바꾸는 즉시 저장한다(설정 화면의 이체 한도와 달리 저장 버튼이 없다).
 * 서버에 부분 수정이 없어 화면이 들고 있는 설정 전체를 보내고, 누른 것이 바로 움직이도록 캐시를 먼저 바꾼 뒤
 * 실패하면 되돌린다 (규칙 10). PUT 은 본문 없이 200 만 주므로 성공한 값은 보낸 값 그대로 두고, 끝나면 서버 값을 다시 받아 맞춘다.
 */
export function useUpdateNotificationSettings() {
  const queryClient = useQueryClient();
  const queryKey = settingsKeys.notifications();

  return useMutation({
    mutationFn: updateNotificationSettings,
    retry: false,
    onMutate: async (next: NotificationSettings) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<NotificationSettings>(queryKey);
      queryClient.setQueryData<NotificationSettings>(queryKey, next);
      return { previous };
    },
    onError: (_error, _next, context) => {
      if (context?.previous !== undefined) queryClient.setQueryData(queryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });
}

export function coachPersonaQueryOptions() {
  return queryOptions({
    queryKey: settingsKeys.coach(),
    queryFn: ({ signal }) => getCoachPersona(signal),
    staleTime: 60_000,
  });
}

export function useCoachPersona() {
  const authStatus = useAuthStore(selectAuthStatus);
  return useQuery({ ...coachPersonaQueryOptions(), enabled: authStatus === "authenticated" });
}

/** 고르는 즉시 저장한다. 알림 설정과 같은 방식으로 캐시를 먼저 바꾸고 실패하면 되돌린다. PUT 본문이 없어 성공 값은 고른 값이다 */
export function useUpdateCoachPersona() {
  const queryClient = useQueryClient();
  const queryKey = settingsKeys.coach();

  return useMutation({
    mutationFn: (persona: CoachPersona) => updateCoachPersona(toCoachPersonaRequest(persona)),
    retry: false,
    onMutate: async (persona: CoachPersona) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<CoachPersona>(queryKey);
      queryClient.setQueryData<CoachPersona>(queryKey, persona);
      return { previous };
    },
    onError: (_error, _persona, context) => {
      if (context?.previous !== undefined) queryClient.setQueryData(queryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });
}
