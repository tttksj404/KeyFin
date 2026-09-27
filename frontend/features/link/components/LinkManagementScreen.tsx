import { useRouter } from "expo-router";
import { TriangleAlert, WalletMinimal } from "lucide-react-native";
import * as React from "react";
import { RefreshControl, View } from "react-native";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useAccounts } from "@/features/account/api/queries";
import { incomeAccountIdOf } from "@/features/account/model";
import { useCreateLinks, useLinkCandidates, useUnlinkAsset } from "@/features/link/api/queries";
import { BankLogoTile } from "@/features/link/components/BankLogoTile";
import { CandidatesErrorState } from "@/features/link/components/CandidatesErrorState";
import { linkErrorMessage, unlinkErrorMessage } from "@/features/link/errors";
import {
  hasNoLinkCandidates,
  linkAssetSubtitle,
  linkRequestFor,
  toLinkManagement,
  unlinkNotice,
  type LinkAssetItem,
  type LinkManagement,
} from "@/features/link/model";
import { cn } from "@/lib/utils";

const MY_ROUTE = "/my";

/** 시각 크기는 시안의 36 버튼을 따르고, 터치 영역은 hitSlop 으로 44 를 채운다 */
const ROW_BUTTON_HIT_SLOP = 4;

/**
 * PAGE-32 연결 관리 (FR-USR-05). GET /links/candidates 의 managed 로 연결된 계좌·카드와 연결하지 않은 자산을 나눈다.
 * 해제는 확인 창을 거쳐 DELETE /links/accounts|cards/{id}, 연결은 행마다 바로 POST /links 로 보낸다(사용자 결정 2026-09-17).
 * 수입 뱃지·해제 경고는 GET /accounts 의 수입 계좌로 채우고, 계좌 목록이 실패해도 화면은 막지 않는다.
 * Pencil PAGE-32 연결 관리 (L6tS7l) · 해제 확인 (gohga) · 불러오는 중 (gKSHA) · 빈 상태 (LjMLH) · 오류 (ksGs8) · 금융망 재연결 (yuG0o).
 */
function LinkManagementScreen() {
  const router = useRouter();
  const candidates = useLinkCandidates();
  const accounts = useAccounts();
  const createLinks = useCreateLinks();
  const unlink = useUnlinkAsset();

  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [unlinkTarget, setUnlinkTarget] = React.useState<LinkAssetItem | null>(null);
  const [actingKey, setActingKey] = React.useState<string | null>(null);

  const busy = createLinks.isPending || unlink.isPending;
  const incomeAccountId = accounts.data === undefined ? undefined : incomeAccountIdOf(accounts.data);
  const errorMessage = unlink.isError
    ? unlinkErrorMessage(unlink.error)
    : createLinks.isError
      ? linkErrorMessage(createLinks.error)
      : null;

  const handleLink = (item: LinkAssetItem) => {
    if (busy) return;
    unlink.reset();
    setActingKey(item.key);
    createLinks.mutate(linkRequestFor(item), { onSettled: () => setActingKey(null) });
  };

  const handleAskUnlink = (item: LinkAssetItem) => {
    if (busy) return;
    setUnlinkTarget(item);
    setDialogOpen(true);
  };

  const handleConfirmUnlink = () => {
    setDialogOpen(false);
    if (unlinkTarget === null || busy) return;
    createLinks.reset();
    setActingKey(unlinkTarget.key);
    unlink.mutate({ kind: unlinkTarget.kind, id: unlinkTarget.id }, { onSettled: () => setActingKey(null) });
  };

  const handleRefresh = () => {
    void candidates.refetch();
    void accounts.refetch();
  };

  return (
    <Screen>
      <ScreenHeader title="연결 관리" onBack={() => (router.canGoBack() ? router.back() : router.replace(MY_ROUTE))} />

      {candidates.isPending ? (
        <ManagementSkeleton />
      ) : candidates.data === undefined ? (
        <View className="flex-1 justify-center pb-20">
          <CandidatesErrorState error={candidates.error} retrying={candidates.isFetching} onRetry={() => candidates.refetch()} />
        </View>
      ) : hasNoLinkCandidates(candidates.data) ? (
        <View className="flex-1 justify-center pb-20">
          <EmptyState
            icon={WalletMinimal}
            title="연결할 자산이 없어요"
            description="금융망에 등록된 계좌·카드가 없습니다. 금융망에서 먼저 등록해 주세요."
          />
        </View>
      ) : (
        <ScreenScrollView
          contentContainerClassName="gap-10 px-6 pb-8"
          refreshControl={<RefreshControl refreshing={candidates.isRefetching && !busy} onRefresh={handleRefresh} />}
        >
          {errorMessage === null ? null : (
            <View className="rounded-lg bg-destructive-muted p-3.5" accessibilityLiveRegion="polite">
              <Text className="text-caption text-destructive">{errorMessage}</Text>
            </View>
          )}
          <ManagementSections
            management={toLinkManagement(candidates.data, incomeAccountId)}
            actingKey={actingKey}
            disabled={busy}
            onLink={handleLink}
            onUnlink={handleAskUnlink}
          />
        </ScreenScrollView>
      )}

      <UnlinkDialog
        open={dialogOpen}
        target={unlinkTarget}
        onCancel={() => setDialogOpen(false)}
        onConfirm={handleConfirmUnlink}
      />
    </Screen>
  );
}

type ManagementSectionsProps = {
  management: LinkManagement;
  actingKey: string | null;
  disabled: boolean;
  onLink: (item: LinkAssetItem) => void;
  onUnlink: (item: LinkAssetItem) => void;
};

// 섹션 제목은 text-h2 검정, 제목과 목록 사이 12 (DESIGN.md 섹션 구분 규칙). 빈 섹션은 그리지 않는다.
function ManagementSections({ management, actingKey, disabled, onLink, onUnlink }: ManagementSectionsProps) {
  const { linkedAccounts, linkedCards, unlinked } = management;
  const row = (item: LinkAssetItem, action: RowAction, withKind: boolean) => (
    <AssetRow
      key={item.key}
      item={item}
      action={action}
      subtitle={linkAssetSubtitle(item, withKind)}
      acting={actingKey === item.key}
      disabled={disabled}
      onPress={() => (action === "link" ? onLink(item) : onUnlink(item))}
    />
  );

  return (
    <>
      {linkedAccounts.length === 0 ? null : (
        <View className="gap-3">
          <SectionTitle title="연결된 계좌" count={linkedAccounts.length} />
          <View className="gap-2">{linkedAccounts.map((item) => row(item, "unlink", false))}</View>
        </View>
      )}
      {linkedCards.length === 0 ? null : (
        <View className="gap-3">
          <SectionTitle title="연결된 카드" count={linkedCards.length} />
          <View className="gap-2">{linkedCards.map((item) => row(item, "unlink", false))}</View>
        </View>
      )}
      {unlinked.length === 0 ? null : (
        <View className="gap-3">
          <View className="gap-1">
            <SectionTitle title="연결하지 않은 자산" count={unlinked.length} />
            <Text className="text-body-sm text-card-foreground">연결하면 이 계좌·카드의 거래도 불러와요.</Text>
          </View>
          <View className="gap-2">{unlinked.map((item) => row(item, "link", true))}</View>
        </View>
      )}
    </>
  );
}

function SectionTitle({ title, count }: { title: string; count: number }) {
  return (
    <Text className="text-h2 tabular-nums text-foreground" accessibilityRole="header">
      {title} {count}
    </Text>
  );
}

type RowAction = "link" | "unlink";

type AssetRowProps = {
  item: LinkAssetItem;
  action: RowAction;
  subtitle: string;
  acting: boolean;
  disabled: boolean;
  onPress: () => void;
};

// Pencil Card (oVrLd): 흰 카드 + 로고 타일 + 이름·마스킹 번호 + 오른쪽 버튼. 연결은 outline, 해제는 secondary.
function AssetRow({ item, action, subtitle, acting, disabled, onPress }: AssetRowProps) {
  const isLink = action === "link";
  const label = isLink ? (acting ? "연결 중…" : "연결") : acting ? "해제 중…" : "해제";

  return (
    <View className="flex-row items-center gap-3 rounded-lg bg-card p-4 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
      <BankLogoTile bankCode={item.bankCode} name={item.logoName} />
      <View className="flex-1 gap-0.5">
        <View className="flex-row items-center gap-1.5">
          <Text className="shrink text-h3 text-foreground" numberOfLines={1}>
            {item.title}
          </Text>
          {item.isIncome === true ? (
            <Badge variant="secondary">
              <Text>수입</Text>
            </Badge>
          ) : null}
        </View>
        <Text className="text-caption tabular-nums text-card-foreground" numberOfLines={1}>
          {subtitle}
        </Text>
      </View>
      <Button
        variant={isLink ? "outline" : "secondary"}
        size="sm"
        className={cn("h-9 rounded-lg px-3.5 sm:h-9", isLink && "border-primary")}
        hitSlop={ROW_BUTTON_HIT_SLOP}
        disabled={disabled}
        onPress={onPress}
        accessibilityLabel={`${item.title} ${subtitle} ${isLink ? "연결" : "연결 해제"}`}
        accessibilityState={{ disabled, busy: acting }}
      >
        <Text className={cn("text-button", isLink ? "text-primary" : "text-secondary-foreground")}>{label}</Text>
      </Button>
    </View>
  );
}

type UnlinkDialogProps = {
  open: boolean;
  /** 닫히는 동안에도 문구가 비지 않도록 마지막 대상을 그대로 받는다 */
  target: LinkAssetItem | null;
  onCancel: () => void;
  onConfirm: () => void;
};

// Pencil 해제 확인 (gohga). 계좌 해제는 수입 계좌 지정도 풀어 이체 제안이 멈추므로 경고 띠를 둔다.
function UnlinkDialog({ open, target, onCancel, onConfirm }: UnlinkDialogProps) {
  const notice = target === null ? null : unlinkNotice(target);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent>
        {notice === null ? null : (
          <>
            <DialogHeader>
              <DialogTitle className="text-h3 text-foreground">{notice.title}</DialogTitle>
              <DialogDescription className="text-body-sm text-card-foreground">{notice.description}</DialogDescription>
            </DialogHeader>
            {notice.incomeWarning === null ? null : (
              <View className="flex-row items-start gap-2 rounded-lg bg-warning-muted p-3.5">
                <Icon as={TriangleAlert} size={18} className="text-warning" />
                <Text className="flex-1 text-caption text-foreground">{notice.incomeWarning}</Text>
              </View>
            )}
            <DialogFooter>
              <Button variant="secondary" onPress={onCancel}>
                <Text>취소</Text>
              </Button>
              <Button variant="destructive" onPress={onConfirm}>
                <Text>해제</Text>
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

const SKELETON_SECTIONS = [
  { id: "accounts", rows: [1, 2] },
  { id: "cards", rows: [1] },
];

function ManagementSkeleton() {
  return (
    <View className="gap-10 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      {SKELETON_SECTIONS.map((section) => (
        <View key={section.id} className="gap-3">
          <Skeleton className="h-6 w-32 rounded-md" />
          {section.rows.map((row) => (
            <Skeleton key={row} className="h-16 w-full rounded-lg" />
          ))}
        </View>
      ))}
    </View>
  );
}

export { LinkManagementScreen };
