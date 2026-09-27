import { useRouter } from "expo-router";
import { Bell, WifiOff } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { flattenNotifications, useMarkNotificationRead, useNotifications } from "@/features/notification/api/queries";
import { announceCoachFeedback } from "@/features/notification/coachFeedback";
import { notificationIcon } from "@/features/notification/catalog";
import {
  groupNotificationsByDate,
  needsAction,
  notificationDateLabel,
  notificationHref,
  notificationTimeLabel,
  type InboxNotification,
  type NotificationDateGroup,
} from "@/features/notification/model";
import { currentDateKey } from "@/lib/date";
import { cn } from "@/lib/utils";

const HOME_ROUTE = "/";

/**
 * PAGE-28 알림함 (FR-NTF-02, P1). 홈 헤더 알림 버튼에서 들어온다.
 * GET /notifications 를 서버 순서(최신순) 그대로 날짜로 묶고, 스크롤 끝에서 다음 쪽을 받는다.
 * 알림을 누르면 읽음 처리(PATCH)를 보내고 응답을 기다리지 않고 종류별 대상 화면으로 간다 — 이동 규칙은 model.notificationHref.
 * 명세의 'requiresAction 건 상단' 은 따르지 않는다: 서버가 id 순으로만 커서를 주고 requiresAction 을 풀지 않아, 올리면 처리한 옛 알림이 계속 위에 남는다.
 * 대신 안 읽은 조치 필요 건에 '확인 필요' 뱃지를 단다.
 * Pencil PAGE-28 알림함 (XZ84O) · 빈 상태 (GRUCR) · 불러오는 중 (C10zu) · 오류 (G8onl0).
 */
function NotificationInboxScreen() {
  const router = useRouter();
  const list = useNotifications();
  const markRead = useMarkNotificationRead();
  const groups = groupNotificationsByDate(flattenNotifications(list.data));
  const todayKey = currentDateKey();

  const open = (notification: InboxNotification) => {
    if (!notification.isRead) markRead.mutate(notification.id);
    // 예산 알림은 코치 피드백을 받아 홈 말풍선으로 전한다 (-184)
    if (notification.type === "BUDGET_ALERT") void announceCoachFeedback(notification.id);
    const href = notificationHref(notification);
    if (href !== null) router.push(href);
  };

  return (
    <Screen>
      <ScreenHeader title="알림" onBack={() => (router.canGoBack() ? router.back() : router.replace(HOME_ROUTE))} />

      {list.isPending ? (
        <InboxSkeleton />
      ) : list.data === undefined ? (
        // 첫 쪽부터 실패했을 때만 화면 전체를 오류로 둔다. 다음 쪽 실패는 목록을 두고 끝에서 다시 부른다.
        <View className="flex-1 justify-center pb-20">
          <EmptyState
            icon={WifiOff}
            title="알림을 불러오지 못했어요"
            description="연결 상태를 확인한 뒤 다시 시도해 주세요."
            action={{ label: "다시 시도", onPress: () => list.refetch(), disabled: list.isFetching }}
          />
        </View>
      ) : (
        <ScreenFlatList
          data={groups}
          keyExtractor={(group) => group.dateKey}
          contentContainerClassName="gap-8 px-6 pb-8"
          renderItem={({ item }) => <DateGroup group={item} todayKey={todayKey} onOpen={open} />}
          onEndReachedThreshold={0.4}
          onEndReached={() => {
            if (list.hasNextPage && !list.isFetchingNextPage) void list.fetchNextPage();
          }}
          refreshing={list.isRefetching && !list.isFetchingNextPage}
          onRefresh={() => list.refetch()}
          ListEmptyComponent={
            <EmptyState icon={Bell} title="아직 받은 알림이 없어요" description="결제 준비·예산·코칭 알림이 오면 여기에 모여요." />
          }
          ListFooterComponent={
            list.isFetchingNextPage ? (
              <Skeleton className="h-24 w-full rounded-lg" />
            ) : list.isFetchNextPageError ? (
              <Pressable accessibilityRole="button" className="items-center py-4" onPress={() => list.fetchNextPage()}>
                <Text className="text-label text-primary">더 불러오지 못했어요. 다시 시도</Text>
              </Pressable>
            ) : null
          }
        />
      )}
    </Screen>
  );
}

type DateGroupProps = {
  group: NotificationDateGroup;
  todayKey: string;
  onOpen: (notification: InboxNotification) => void;
};

// 날짜 묶음 제목은 결제 캘린더와 같이 text-h3 검정으로 둔다 (DESIGN.md 섹션 구분 규칙).
function DateGroup({ group, todayKey, onOpen }: DateGroupProps) {
  return (
    <View className="gap-3">
      <Text className="text-h3 text-foreground" accessibilityRole="header">
        {notificationDateLabel(group.dateKey, todayKey)}
      </Text>
      <View className="gap-2">
        {group.notifications.map((notification) => (
          <NotificationCard key={notification.id} notification={notification} onPress={() => onOpen(notification)} />
        ))}
      </View>
    </View>
  );
}

type NotificationCardProps = {
  notification: InboxNotification;
  onPress: () => void;
};

// Pencil Card: 흰 카드 + 아이콘 타일 + 제목(안 읽음은 굵게·점) · 본문 · 뱃지와 시각. 읽음 여부는 점만이 아니라 제목 굵기와 읽기 문구로도 전한다 (규칙 40).
function NotificationCard({ notification, onPress }: NotificationCardProps) {
  const unread = !notification.isRead;
  const action = needsAction(notification);
  const time = notificationTimeLabel(notification);
  const openable = notificationHref(notification) !== null;
  const label = [unread ? "읽지 않음" : null, action ? "확인 필요" : null, notification.title, notification.body, time]
    .filter((part) => part !== null)
    .join(", ");

  return (
    <Pressable
      className="flex-row items-start gap-3 rounded-lg bg-card p-4 active:opacity-70 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none"
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={openable ? "읽음으로 표시하고 관련 화면을 엽니다" : "읽음으로 표시합니다"}
      onPress={onPress}
    >
      <View className="h-10 w-10 items-center justify-center rounded-full bg-accent">
        <Icon as={notificationIcon(notification.type)} size={20} className="text-primary" />
      </View>
      <View className="flex-1 gap-1">
        <View className="flex-row items-center gap-1.5">
          <Text className={cn("flex-1 text-foreground", unread ? "text-h3" : "text-body")} numberOfLines={2}>
            {notification.title}
          </Text>
          {unread ? <View className="h-2 w-2 rounded-full bg-primary" accessible={false} /> : null}
        </View>
        {notification.body === null ? null : (
          <Text className="text-body-sm text-card-foreground" numberOfLines={3}>
            {notification.body}
          </Text>
        )}
        <View className="flex-row items-center gap-1.5">
          {action ? (
            <View className="rounded-sm bg-accent px-1.5 py-0.5">
              <Text className="text-caption text-primary">확인 필요</Text>
            </View>
          ) : null}
          <Text className="text-caption tabular-nums text-card-foreground">{time}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const SKELETON_GROUPS = [
  { id: "today", rows: [1, 2] },
  { id: "yesterday", rows: [1, 2] },
];

// Pencil 불러오는 중 (C10zu): 날짜 제목 자리 + 카드 자리.
function InboxSkeleton() {
  return (
    <View className="gap-8 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      {SKELETON_GROUPS.map((group) => (
        <View key={group.id} className="gap-3">
          <Skeleton className="h-6 w-16 rounded-sm" />
          {group.rows.map((row) => (
            <Skeleton key={row} className="h-24 w-full rounded-lg" />
          ))}
        </View>
      ))}
    </View>
  );
}

export { NotificationInboxScreen };
