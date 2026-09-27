import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { Coins, Store, WifiOff } from "lucide-react-native";
import * as React from "react";
import { Image, Pressable, View } from "react-native";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Screen, ScreenFlatList } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { roomKeys } from "@/features/room/api/queries";
import { furnitureGroupOf, isFurnitureGroup, roomItemThumbnailGeometry } from "@/features/room/catalog";
import type { FurnitureGroup } from "@/features/room/catalog";
import { FurnitureThumbnail } from "@/features/room/components/FurnitureThumbnail";
import { EDIT_FROM_SHOP } from "@/features/room/components/RoomEditScreen";
import { isOutfitKey } from "@/features/room/outfits";
import { FilterSelect, type SelectOption } from "@/features/transaction/components/FilterSelect";
import { useCoinBalance, usePurchaseShopItem, useShopItems } from "@/features/shop/api/queries";
import { SHOP_FURNITURE_GROUPS, shopCategoryIcon, shopItemSprite } from "@/features/shop/catalog";
import { shopPurchaseErrorMessage } from "@/features/shop/errors";
import {
  canBuyShopItem,
  coinCountLabel,
  shopCategoryFilterKey,
  shopGroupFilterKey,
  shopGroupsWithItems,
  shopItemsForFilter,
  shopPriceLabel,
  type ShopFilterKey,
  type ShopItem,
} from "@/features/shop/model";
import { cn } from "@/lib/utils";

const HOME_ROUTE = "/";
/** 산 뒤 옷을 입는 곳. 장착은 옷장에서만 한다 (사용자 결정 2026-09-21) */
const WARDROBE_ROUTE = "/character/wardrobe";
/** 산 뒤 가구를 놓는 곳 */
const ROOM_EDIT_ROUTE = "/room/edit";
/** 그림은 4px 스케일 밖 크기라 style 로 준다 (BankLogoTile 과 같은 방식) */
const SPRITE_SIZE = 72;
/** 의상 세트 그림은 상·하의·신발이 가로로 놓여 있어(512×208) 정사각 자리에 넣으면 옷이 너무 작아진다 */
const OUTFIT_SPRITE_STYLE = { width: "100%", height: 72 } as const;
const GROUP_TITLE = "분류";
const ALL_GROUPS_KEY = "all";

/** 옷·가구 탭 (사용자 요청 2026-09-23 "옷, 가구 탭 구분 확실히" — 선택창 한 개 안의 구역 제목만으로는 둘이 갈라져 보이지 않았다) */
type ShopTab = "AVATAR" | "FURNITURE";
const SHOP_TABS: readonly { key: ShopTab; label: string }[] = [
  { key: "AVATAR", label: "옷" },
  { key: "FURNITURE", label: "가구" },
];

/**
 * 가구 탭의 분류 선택창 — '가구 전체' 아래에 분류(침대·소파 … 식물). 파는 상품이 있는 분류만 보인다(사용자 요청 2026-09-21).
 * 옷은 세트 한 벌이라 부위로 나누지 않으므로 옷 탭에는 선택창이 없다 (사용자 결정 2026-09-21).
 * 부위(slot)를 모르는 상품도 카테고리는 있어 두 탭 중 한쪽 '전체'에 그대로 보인다 (규칙 90).
 */
function groupOptions(items: readonly ShopItem[]): SelectOption[] {
  const present = new Set(shopGroupsWithItems(items, SHOP_FURNITURE_GROUPS.map(({ group }) => group), furnitureGroupOf));
  return [
    { key: ALL_GROUPS_KEY, label: "가구 전체" },
    ...SHOP_FURNITURE_GROUPS.filter(({ group }) => present.has(group)).map(({ group, label, section }) => ({ key: group, label, section })),
  ];
}

/** 탭·분류 → 목록 필터 값. 옷 탭은 옷 전체, 가구 탭은 분류가 있으면 그 분류, 없으면 가구 전체 */
function filterKeyOf(tab: ShopTab, group: FurnitureGroup | null): ShopFilterKey {
  if (tab === "AVATAR") return shopCategoryFilterKey("AVATAR");
  return group === null ? shopCategoryFilterKey("FURNITURE") : shopGroupFilterKey(group);
}

/**
 * PAGE-29 상점 (FR-GAM-05, P1). 홈 상점 버튼에서 들어온다.
 * `GET /shop` 은 판매 중인 상품을 한 번에 주므로(페이지 없음) 한 번 받아 선택창으로 걸러 보여 준다 — 값을 바꿔도 다시 부르지 않는다.
 * 구매는 코인이 빠지는 일이라 확인 창을 거치고, 요청 중에는 창을 닫지도 다시 누르지도 못한다 (규칙 80).
 * 보유한 상품은 다시 살 수 없고(서버도 409 SHOP_002 로 막는다) 누르면 쓰는 곳으로 간다. 코인이 모자라면 가격 옆에 이유를 적는다.
 * 입고 놓는 것은 옷장·방 꾸미기에서만 한다 — 장착 지점이 한 곳이어야 방금 산 것과 예전에 산 것을 같은 자리에서 다룬다 (사용자 결정 2026-09-21).
 * Pencil 시안 없음 — design/DESIGN.md 의 카드·칩 규칙을 따랐다.
 */
function ShopScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const items = useShopItems();
  const balance = useCoinBalance();
  const purchase = usePurchaseShopItem();
  const [tab, setTab] = React.useState<ShopTab>("AVATAR");
  /** 가구 탭의 분류. null 은 가구 전체. 탭을 옮겨도 남겨 두어 가구 탭으로 돌아오면 보던 분류가 그대로다 */
  const [group, setGroup] = React.useState<FurnitureGroup | null>(null);
  const [target, setTarget] = React.useState<ShopItem | null>(null);
  const [bought, setBought] = React.useState<ShopItem | null>(null);

  const all = items.data ?? [];
  const shown = shopItemsForFilter(all, filterKeyOf(tab, group), furnitureGroupOf);

  const openPurchase = (item: ShopItem) => {
    purchase.reset();
    setTarget(item);
  };

  const closePurchase = () => {
    if (purchase.isPending) return;
    purchase.reset();
    setTarget(null);
  };

  const confirmPurchase = () => {
    if (target === null || purchase.isPending) return;
    const item = target;
    purchase.mutate(
      { itemId: item.itemId },
      {
        onSuccess: () => {
          setTarget(null);
          // 산 것을 어디서 쓰는지 이어서 알려 준다. 입고 놓는 것은 옷장·방 꾸미기에서만 하고 여기서는 데려다 주기만 한다
          // — 장착 지점이 한 곳이어야 예전에 산 것과 방금 산 것을 같은 자리에서 다룬다 (사용자 결정 2026-09-21).
          setBought(item);
          // 가구를 사면 방 꾸미기 목록에도 생긴다. 방 쿼리가 이미 shopKeys 를 쓰고 있어 반대 방향 import 는 순환이라 여기서 무효화한다.
          void queryClient.invalidateQueries({ queryKey: roomKeys.all });
        },
      }
    );
  };

  /** 옷은 옷장에서, 가구는 방 꾸미기에서 쓴다 — 산 직후든 예전에 산 것이든 쓰는 자리는 같다 */
  // 가구는 놓으러 가는 길이라 방 꾸미기가 보관함을 펴 둔 채로 열리게 어디서 왔는지 알린다
  const openPlaceFor = (item: ShopItem) =>
    router.push(item.category === "FURNITURE" ? { pathname: ROOM_EDIT_ROUTE, params: { from: EDIT_FROM_SHOP } } : WARDROBE_ROUTE);

  const openBoughtPlace = () => {
    if (bought === null) return;
    const item = bought;
    setBought(null);
    openPlaceFor(item);
  };

  return (
    <Screen>
      <ScreenHeader
        title="상점"
        onBack={() => (router.canGoBack() ? router.back() : router.replace(HOME_ROUTE))}
        right={<CoinBadge balance={balance.data} pending={balance.isPending} />}
      />

      {/* 자산 탭(계좌·카드)과 같은 탭 모양. 고른 탭은 primary 로 채워 어느 쪽인지 한눈에 보인다 */}
      <View className="flex-row gap-2 px-6 pb-3" accessibilityRole="tablist">
        {SHOP_TABS.map(({ key, label }) => (
          <Pressable
            key={key}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === key }}
            onPress={() => setTab(key)}
            className={cn("h-10 flex-1 items-center justify-center rounded-md", tab === key ? "bg-primary" : "bg-accent")}
          >
            <Text className={cn("text-label", tab === key ? "text-primary-foreground" : "text-card-foreground")}>{label}</Text>
          </Pressable>
        ))}
      </View>
      {tab === "FURNITURE" ? (
        <View className="flex-row px-6 pb-4">
          <FilterSelect
            title={GROUP_TITLE}
            options={groupOptions(all)}
            selectedKey={group ?? ALL_GROUPS_KEY}
            onSelect={(key) => setGroup(isFurnitureGroup(key) ? key : null)}
          />
        </View>
      ) : (
        <View className="pb-1" />
      )}

      {items.isPending ? (
        <ShopSkeleton />
      ) : items.data === undefined ? (
        <EmptyState
          icon={WifiOff}
          title="상점을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: () => items.refetch(), disabled: items.isFetching }}
        />
      ) : (
        <ScreenFlatList
          overlapHeader={false}
          data={shown}
          numColumns={2}
          keyExtractor={(item) => String(item.itemId)}
          renderItem={({ item }) => (
            <ShopItemCard item={item} balance={balance.data} onPress={openPurchase} onOpenOwned={openPlaceFor} />
          )}
          columnWrapperClassName="gap-3"
          contentContainerClassName="gap-3 px-6 pb-8"
          refreshing={items.isRefetching}
          onRefresh={() => items.refetch()}
          ListEmptyComponent={
            <EmptyState icon={Store} title="이 종류에 파는 상품이 없어요" description="다른 종류를 골라 보세요." />
          }
        />
      )}

      <PurchaseDialog
        item={target}
        balance={balance.data}
        pending={purchase.isPending}
        error={purchase.isError ? shopPurchaseErrorMessage(purchase.error) : null}
        onCancel={closePurchase}
        onConfirm={confirmPurchase}
      />

      <PurchasedDialog item={bought} onClose={() => setBought(null)} onOpenPlace={openBoughtPlace} />
    </Screen>
  );
}

// 산 직후에만 뜬다. 여기서 입히지는 않는다 — 입고 놓는 곳은 옷장·방 꾸미기 한 곳뿐이라 거기로 데려다 주기만 한다.
function PurchasedDialog({ item, onClose, onOpenPlace }: { item: ShopItem | null; onClose: () => void; onOpenPlace: () => void }) {
  if (item === null) return null;
  const furniture = item.category === "FURNITURE";

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-h3 text-foreground">새 {furniture ? "가구" : "옷"}을 샀어요</DialogTitle>
          <DialogDescription className="text-body-sm text-card-foreground">
            {item.name} · {furniture ? "방 꾸미기에서 원하는 자리에 놓을 수 있어요." : "옷장에서 입으면 방 안 캐릭터가 바로 갈아입어요."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" className="h-button-md rounded-lg" onPress={onClose}>
            <Text>나중에</Text>
          </Button>
          <Button className="h-button-md rounded-lg" onPress={onOpenPlace}>
            <Text>{furniture ? "방 꾸미기 열기" : "옷장 열기"}</Text>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// 헤더 오른쪽 보유 코인. 코인 이력(PAGE-30)과 같은 노란 코인 원이다.
function CoinBadge({ balance, pending }: { balance: number | undefined; pending: boolean }) {
  const count = balance === undefined ? null : coinCountLabel(balance);

  return (
    <View
      className="h-9 flex-row items-center gap-1.5 rounded-full bg-accent px-3"
      accessible={count !== null}
      accessibilityLabel={count === null ? undefined : `보유 코인 ${count}개`}
      accessibilityLiveRegion="polite"
    >
      <View className="h-5 w-5 items-center justify-center rounded-full bg-warning" accessible={false}>
        <Icon as={Coins} size={12} className="text-foreground" />
      </View>
      {pending ? <Skeleton className="h-4 w-10 rounded-sm" /> : <Text className="text-label tabular-nums text-foreground">{count ?? "—"}</Text>}
    </View>
  );
}

type ShopItemCardProps = {
  item: ShopItem;
  balance: number | undefined;
  onPress: (item: ShopItem) => void;
  /** 보유한 상품을 눌렀을 때. 사는 대신 쓰는 곳(옷장·방 꾸미기)으로 데려간다 */
  onOpenOwned: (item: ShopItem) => void;
};

// 코인이 모자라면 누를 수 없다 — 상태를 색만으로 전하지 않고 가격 자리의 문구로도 적는다 (규칙 40).
// 보유한 상품은 살 수는 없지만 누르면 쓰는 곳으로 간다. 눌리지 않으면 산 옷을 상점에서 보고도 입으러 갈 길이 없다.
function ShopItemCard({ item, balance, onPress, onOpenOwned }: ShopItemCardProps) {
  const sprite = shopItemSprite(item.assetKey);
  const buyable = canBuyShopItem(item, balance);
  const price = shopPriceLabel(item.price);
  const shortage = !item.owned && !buyable;
  const furniture = item.category === "FURNITURE";

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.name}, ${item.price === 0 ? "무료" : `${price}코인`}${item.owned ? ", 보유 중" : shortage ? ", 코인 부족" : ""}`}
      accessibilityHint={item.owned ? (furniture ? "누르면 방 꾸미기를 엽니다" : "누르면 옷장을 엽니다") : undefined}
      accessibilityState={{ disabled: !item.owned && !buyable }}
      disabled={!item.owned && !buyable}
      onPress={() => (item.owned ? onOpenOwned(item) : onPress(item))}
      className={cn(
        "flex-1 gap-2 overflow-visible rounded-2xl bg-card p-3 shadow shadow-black/10 active:opacity-80 dark:border dark:border-border dark:shadow-none",
        // 코인이 모자라 못 사는 것만 흐리게 둔다 — 보유한 상품은 눌러서 쓰러 갈 수 있으므로 흐리면 안 눌린다고 읽힌다.
        shortage && "opacity-60"
      )}
    >
      <View className="h-24 items-center justify-center overflow-visible rounded-xl bg-muted" accessible={false}>
        {sprite === null ? (
          <Icon as={shopCategoryIcon(item.category)} size={28} className="text-card-foreground" />
        ) : isOutfitKey(item.assetKey) ? (
          <Image
            source={sprite}
            style={OUTFIT_SPRITE_STYLE}
            resizeMode="contain"
            accessible={false}
          />
        ) : (
          <FurnitureThumbnail source={sprite} geometry={roomItemThumbnailGeometry(item.assetKey)} size={SPRITE_SIZE} />
        )}
      </View>
      <Text className="text-body-sm text-foreground" numberOfLines={1}>
        {item.name}
      </Text>
      <View className="flex-row items-center gap-1.5">
        {item.owned ? null : <Icon as={Coins} size={14} className="text-warning" />}
        <Text className={cn("text-label tabular-nums", buyable ? "text-foreground" : "text-card-foreground")}>
          {item.owned ? "보유 중" : price}
        </Text>
        {item.owned ? <Text className="text-caption text-card-foreground">{furniture ? "놓으러 가기" : "입으러 가기"}</Text> : null}
        {shortage ? <Text className="text-caption text-card-foreground">코인 부족</Text> : null}
      </View>
    </Pressable>
  );
}

type PurchaseDialogProps = {
  item: ShopItem | null;
  balance: number | undefined;
  pending: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

// 코인이 빠지는 일이라 무엇을 얼마에 사는지, 사고 나면 얼마가 남는지 보여 준 뒤에만 보낸다.
function PurchaseDialog({ item, balance, pending, error, onCancel, onConfirm }: PurchaseDialogProps) {
  if (item === null) return null;
  const after = balance === undefined ? null : coinCountLabel(balance - item.price);

  return (
    <Dialog open onOpenChange={(next) => !next && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-h3 text-foreground">{item.name} 살까요?</DialogTitle>
          <DialogDescription className="text-body-sm text-card-foreground">
            {item.price === 0 ? "무료 상품이에요." : `${shopPriceLabel(item.price)}코인이 빠져나가요.`}
            {after === null ? "" : ` 사고 나면 ${after}코인이 남아요.`}
          </DialogDescription>
        </DialogHeader>
        {error === null ? null : (
          <View className="rounded-lg bg-destructive-muted p-3.5" accessibilityLiveRegion="polite">
            <Text className="text-caption text-foreground">{error}</Text>
          </View>
        )}
        <DialogFooter>
          <Button variant="secondary" disabled={pending} onPress={onCancel}>
            <Text>취소</Text>
          </Button>
          <Button disabled={pending} onPress={onConfirm}>
            <Text>{pending ? "구매 중" : "구매"}</Text>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const SKELETON_ROWS = [1, 2, 3];

function ShopSkeleton() {
  return (
    <View className="gap-3 px-6" accessible accessibilityLabel="불러오는 중">
      {SKELETON_ROWS.map((row) => (
        <View key={row} className="flex-row gap-3">
          <Skeleton className="h-40 flex-1 rounded-2xl" />
          <Skeleton className="h-40 flex-1 rounded-2xl" />
        </View>
      ))}
    </View>
  );
}

export { ShopScreen };
