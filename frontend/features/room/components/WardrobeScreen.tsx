import { useRouter } from "expo-router";
import { Shirt, Store, WifiOff } from "lucide-react-native";
import { Image, Pressable, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useUpdateItemEquipment, useUserItems } from "@/features/room/api/queries";
import { itemEquipmentErrorMessage } from "@/features/room/errors";
import { wornItem, type UserItem } from "@/features/room/items";
import { outfitByAssetKey } from "@/features/room/outfits";
import { cn } from "@/lib/utils";

const HOME_ROUTE = "/";
const SHOP_ROUTE = "/shop";
/** 서 있는 그림은 4px 스케일 밖 크기라 style 로 준다. 세로로 긴 그림이라 자리도 카드보다 높다 */
const OUTFIT_STYLE = { width: 88, height: 120 } as const;

/**
 * 옷장 (FR-GAM-05, P1). 홈 옷장 버튼에서 들어오며 명세에 독립 PAGE 번호는 없다.
 * `GET /items` 는 보유 아이템을 한 번에 주므로(페이지 없음) 한 번 받아 그대로 보여 준다 —
 * 옷은 세트 한 벌이라 부위로 나누지 않는다(features/room/outfits.ts, 사용자 결정 2026-09-21).
 * 누르면 바로 입고 다시 누르면 벗는다 — 코인이 들지 않고 되돌릴 수 있어 확인 창을 두지 않는다.
 * 세트는 한 번에 한 벌이고 기존 것은 서버가 자동으로 벗기므로, 응답(전체 착장)으로 목록을 다시 맞춘다.
 * 카드에는 그 세트를 입은 모습을 그려 고르기 전에 차림을 알 수 있게 했다.
 * Pencil 시안 없음 — design/DESIGN.md 의 카드·칩 규칙을 따랐다.
 */
function WardrobeScreen() {
  const router = useRouter();
  const items = useUserItems();
  const equipment = useUpdateItemEquipment();

  const shown = items.data ?? [];
  const wearing = wornItem(shown);
  const changingId = equipment.isPending ? equipment.variables.userItemId : null;

  const toggle = (item: UserItem) => {
    if (equipment.isPending) return;
    equipment.mutate({ userItemId: item.userItemId, equipped: !item.equipped });
  };

  return (
    <Screen>
      <ScreenHeader title="옷장" onBack={() => (router.canGoBack() ? router.back() : router.replace(HOME_ROUTE))} />

      {equipment.isError ? (
        <View className="mx-6 mb-3 rounded-lg bg-destructive-muted p-3.5" accessibilityLiveRegion="polite">
          <Text className="text-caption text-foreground">{itemEquipmentErrorMessage(equipment.error)}</Text>
        </View>
      ) : null}

      {items.isPending ? (
        <WardrobeSkeleton />
      ) : items.data === undefined ? (
        <EmptyState
          icon={WifiOff}
          title="옷장을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => items.refetch(), disabled: items.isFetching }}
        />
      ) : (
        <ScreenFlatList
          overlapHeader={false}
          data={shown}
          numColumns={2}
          keyExtractor={(item) => String(item.userItemId)}
          renderItem={({ item }) => (
            <ItemCard item={item} changing={item.userItemId === changingId} disabled={equipment.isPending} onPress={toggle} />
          )}
          columnWrapperClassName="gap-3"
          contentContainerClassName="gap-3 px-6 pb-8"
          ListHeaderComponent={<WearingLine wearing={wearing} />}
          refreshing={items.isRefetching}
          onRefresh={() => items.refetch()}
          ListEmptyComponent={
            <EmptyState
              icon={Store}
              title="가진 옷이 없어요"
              description="상점에서 코인으로 옷 세트를 살 수 있어요."
              action={{ label: "상점 가기", onPress: () => router.push(SHOP_ROUTE) }}
            />
          }
        />
      )}
    </Screen>
  );
}

// 지금 입은 것을 한 줄로 알려 준다 — 카드의 '착용 중' 뱃지만으로는 목록을 훑어야 알 수 있다.
function WearingLine({ wearing }: { wearing: UserItem | null }) {
  return (
    <Text className="pb-1 text-body-sm text-card-foreground" accessibilityLiveRegion="polite">
      {wearing === null ? "기본 차림이에요." : `지금 ${wearing.name}을 입고 있어요.`}
    </Text>
  );
}

type ItemCardProps = {
  item: UserItem;
  /** 이 카드가 지금 바뀌는 중 */
  changing: boolean;
  /** 다른 카드가 바뀌는 중이라 잠깐 누를 수 없다 */
  disabled: boolean;
  onPress: (item: UserItem) => void;
};

// 입은 것은 테두리와 '착용 중' 문구로 함께 표시한다 — 색만으로 전하지 않는다 (규칙 40).
function ItemCard({ item, changing, disabled, onPress }: ItemCardProps) {
  const state = changing ? "바꾸는 중" : item.equipped ? "착용 중" : "누르면 입어요";
  const outfit = outfitByAssetKey(item.assetKey);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.name}, ${item.equipped ? "착용 중" : "벗은 상태"}`}
      accessibilityHint={item.equipped ? "누르면 벗어요" : "누르면 입어요"}
      accessibilityState={{ selected: item.equipped, disabled, busy: changing }}
      disabled={disabled}
      onPress={() => onPress(item)}
      className={cn(
        "flex-1 gap-2 rounded-2xl bg-card p-3 shadow shadow-black/10 active:opacity-80 dark:border dark:border-border dark:shadow-none",
        item.equipped && "border-2 border-primary",
        disabled && !changing && "opacity-60"
      )}
    >
      <View className="h-32 items-center justify-center rounded-xl bg-muted" accessible={false}>
        {outfit === null ? (
          <Icon as={Shirt} size={28} className={item.equipped ? "text-primary" : "text-card-foreground"} />
        ) : (
          <Image source={outfit.standing} style={OUTFIT_STYLE} resizeMode="contain" accessible={false} />
        )}
      </View>
      <Text className="text-body-sm text-foreground" numberOfLines={1}>
        {item.name}
      </Text>
      <Text className={cn("text-caption", item.equipped ? "text-primary" : "text-card-foreground")}>{state}</Text>
    </Pressable>
  );
}

const SKELETON_ROWS = [1, 2];

function WardrobeSkeleton() {
  return (
    <View className="gap-3 px-6" accessible accessibilityLabel="불러오는 중">
      <Skeleton className="h-5 w-40 rounded-sm" />
      {SKELETON_ROWS.map((row) => (
        <View key={row} className="flex-row gap-3">
          <Skeleton className="h-52 flex-1 rounded-2xl" />
          <Skeleton className="h-52 flex-1 rounded-2xl" />
        </View>
      ))}
    </View>
  );
}

export { WardrobeScreen };
