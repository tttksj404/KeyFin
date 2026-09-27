import { useRouter } from "expo-router";
import { CreditCard, Info, TriangleAlert, WifiOff } from "lucide-react-native";
import type { ReactNode } from "react";
import { RefreshControl, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useLinkCandidates } from "@/features/link/api/queries";
import { BankLogoTile } from "@/features/link/components/BankLogoTile";
import type { LinkCard } from "@/features/link/model";
import { useCardBillingDetail } from "@/features/payment/api/queries";
import { isCardNotFoundError } from "@/features/payment/errors";
import {
  billingDateLabel,
  billingStatusLabel,
  cardBillingCycleCaption,
  cardBillingNotice,
  statementCaption,
  statementRangeLabel,
  statementTitle,
  type BillingStatus,
  type CardBillingApproval,
  type CardBillingDetail,
  type CardBillingStatement,
} from "@/features/payment/model";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

const ASSETS_ROUTE = "/assets";

type CardBillingDetailScreenProps = {
  /** 라우트 파라미터에서 검증한 카드 id. 형식이 틀리면 null */
  cardId: number | null;
};

/**
 * PAGE-33 카드 청구 상세 (FR-BGT-06, P1). 자산 탭 카드 행과 결제 캘린더의 카드 청구 항목에서 들어온다.
 * GET /cards/{id}/billings 의 이번 주기 예정액·근거 승인과 발행된 청구서를 보여 준다. 금액·상태·출금일은 서버 값 그대로다 (규칙 80).
 * 발급사·마스킹 번호는 이 응답에 없어 금융망 후보에서 cardId 로 찾고, 후보를 못 받으면 그 줄만 빠진다.
 * Pencil PAGE-33 카드 청구 상세 (LsAZT) · 내역 없음·출금일 모름 (AcQNS) · 불러오는 중 (H5Wkz) · 오류 (yf3NJ) · 못 찾음 (u8EwPt).
 */
function CardBillingDetailScreen({ cardId }: CardBillingDetailScreenProps) {
  const router = useRouter();
  const detail = useCardBillingDetail(cardId);
  const candidates = useLinkCandidates();
  const notFound = cardId === null || isCardNotFoundError(detail.error);
  const identity = candidates.data?.cards.find((card) => card.id === cardId) ?? null;

  const goBack = () => (router.canGoBack() ? router.back() : router.replace(ASSETS_ROUTE));

  return (
    <Screen>
      <ScreenHeader title="카드 청구" onBack={goBack} />

      {notFound ? (
        <CenteredState>
          <EmptyState
            icon={CreditCard}
            title="카드를 찾을 수 없어요"
            description="없는 카드이거나 주소가 잘못됐어요. 자산 탭에서 카드를 다시 골라 주세요."
            action={{ label: "자산 탭으로", onPress: () => router.replace(ASSETS_ROUTE) }}
          />
        </CenteredState>
      ) : detail.isPending ? (
        <DetailSkeleton />
      ) : detail.data === undefined ? (
        <CenteredState>
          <EmptyState
            icon={WifiOff}
            title="청구 내역을 불러오지 못했어요"
            description="연결 상태를 확인한 뒤 다시 시도해 주세요."
            action={{ label: "다시 시도", onPress: () => detail.refetch(), disabled: detail.isFetching }}
          />
        </CenteredState>
      ) : (
        <ScreenScrollView
          contentContainerClassName="gap-10 px-6 pb-8"
          refreshControl={<RefreshControl refreshing={detail.isRefetching} onRefresh={() => detail.refetch()} />}
        >
          <BillingSummary detail={detail.data} identity={identity} />
          <ApprovalSection approvals={detail.data.approvals} />
          <StatementSection detail={detail.data} />
        </ScreenScrollView>
      )}
    </Screen>
  );
}

function CenteredState({ children }: { children: ReactNode }) {
  return <View className="flex-1 justify-center pb-20">{children}</View>;
}

type BillingSummaryProps = {
  detail: CardBillingDetail;
  /** 금융망 후보의 같은 카드. 못 받았으면 null 이라 발급사·번호 줄을 생략한다 */
  identity: LinkCard | null;
};

// Pencil Summary: 로고 타일 + 카드 이름·발급사·마스킹 번호, 예정액(amount-lg)과 기간 한 줄, 확정 전이라는 안내 띠.
function BillingSummary({ detail, identity }: BillingSummaryProps) {
  const caption = cardBillingCycleCaption(detail);
  const amount = formatKRW(detail.estimatedAmount);

  return (
    <View className="gap-5">
      <View className="flex-row items-center gap-3">
        <BankLogoTile name={identity?.issuerName ?? detail.cardName} />
        <View className="flex-1 gap-0.5">
          <Text className="text-h3 text-foreground" numberOfLines={1}>
            {detail.cardName}
          </Text>
          {identity === null ? null : (
            <Text className="text-caption tabular-nums text-card-foreground" numberOfLines={1}>
              {identity.issuerName} · {identity.maskedNo}
            </Text>
          )}
        </View>
      </View>
      <View className="gap-1" accessible accessibilityLabel={`이번 주 청구 예정 ${amount}, ${caption}`}>
        <Text className="text-label text-card-foreground">이번 주 청구 예정</Text>
        <Text className="text-amount-lg tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
          {amount}
        </Text>
        <Text className="text-caption tabular-nums text-card-foreground">{caption}</Text>
      </View>
      <BillingNotice detail={detail} />
    </View>
  );
}

function BillingNotice({ detail }: { detail: CardBillingDetail }) {
  const notice = cardBillingNotice(detail);
  const warning = notice.tone === "warning";

  return (
    <View className={cn("flex-row items-start gap-2 rounded-lg p-3.5", warning ? "bg-warning-muted" : "bg-info-muted")}>
      <Icon as={warning ? TriangleAlert : Info} size={18} className={warning ? "text-warning" : "text-info"} />
      <Text className="flex-1 text-caption text-foreground">{notice.message}</Text>
    </View>
  );
}

// 섹션 제목은 text-h2 검정 + 건수 (DESIGN.md 섹션 구분 규칙). 행은 카드가 아니라 아래 선으로 나눈다 (Pencil Row stroke bottom).
function ApprovalSection({ approvals }: { approvals: CardBillingApproval[] }) {
  return (
    <View className="gap-3">
      <SectionTitle title="승인 내역" count={approvals.length} />
      {approvals.length === 0 ? (
        <EmptyBox message="이번 주 승인 내역이 없어요." />
      ) : (
        <View>
          {approvals.map((approval) => (
            <ApprovalRow key={approval.transactionId} approval={approval} />
          ))}
        </View>
      )}
    </View>
  );
}

function ApprovalRow({ approval }: { approval: CardBillingApproval }) {
  const date = billingDateLabel(approval.date);
  const amount = formatKRW(approval.amount);

  return (
    <View
      className="flex-row items-center gap-3 border-b border-border py-3.5"
      accessible
      accessibilityLabel={`${approval.merchantName}, ${date}, ${amount}`}
    >
      <View className="flex-1 gap-0.5">
        <Text className="text-body text-foreground" numberOfLines={1}>
          {approval.merchantName}
        </Text>
        <Text className="text-caption tabular-nums text-card-foreground">{date}</Text>
      </View>
      <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
        {amount}
      </Text>
    </View>
  );
}

// 출금일이 지났는지는 기기 시계가 아니라 응답의 기준일(asOf)로 판단한다.
function StatementSection({ detail }: { detail: CardBillingDetail }) {
  return (
    <View className="gap-3">
      <View className="gap-1">
        <SectionTitle title="청구서" count={detail.statements.length} />
        <Text className="text-body-sm text-card-foreground">{statementRangeLabel(detail)}</Text>
      </View>
      {detail.statements.length === 0 ? (
        <EmptyBox message="발행된 청구서가 없어요." />
      ) : (
        <View>
          {detail.statements.map((statement) => (
            <StatementRow key={statement.billingId} statement={statement} caption={statementCaption(statement, detail.asOf)} />
          ))}
        </View>
      )}
    </View>
  );
}

const STATUS_BADGE_CLASSES: Record<BillingStatus, { box: string; text: string }> = {
  UNPAID: { box: "bg-destructive-muted", text: "text-destructive" },
  PAID: { box: "bg-positive-muted", text: "text-positive" },
  UNKNOWN: { box: "bg-muted", text: "text-card-foreground" },
};

// 상태는 색만으로 전하지 않고 뱃지 글자로 함께 쓴다 (규칙 40).
function StatementRow({ statement, caption }: { statement: CardBillingStatement; caption: string }) {
  const title = statementTitle(statement);
  const status = billingStatusLabel(statement.status);
  const amount = formatKRW(statement.amount);
  const badge = STATUS_BADGE_CLASSES[statement.status];

  return (
    <View
      className="flex-row items-center gap-3 border-b border-border py-3.5"
      accessible
      accessibilityLabel={`${title}, ${status}, ${caption}, ${amount}`}
    >
      <View className="flex-1 gap-0.5">
        <View className="flex-row items-center gap-1.5">
          <Text className="shrink text-body text-foreground" numberOfLines={1}>
            {title}
          </Text>
          <View className={cn("rounded-sm px-1.5 py-0.5", badge.box)}>
            <Text className={cn("text-caption", badge.text)}>{status}</Text>
          </View>
        </View>
        <Text className="text-caption tabular-nums text-card-foreground">{caption}</Text>
      </View>
      <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
        {amount}
      </Text>
    </View>
  );
}

function SectionTitle({ title, count }: { title: string; count: number }) {
  return (
    <Text className="text-h2 tabular-nums text-foreground" accessibilityRole="header">
      {title} {count}
    </Text>
  );
}

function EmptyBox({ message }: { message: string }) {
  return (
    <View className="rounded-lg bg-muted p-4">
      <Text className="text-body-sm text-card-foreground">{message}</Text>
    </View>
  );
}

const SKELETON_SECTIONS = [
  { id: "approvals", rows: [1, 2, 3] },
  { id: "statements", rows: [1, 2] },
];

// Pencil 불러오는 중 (H5Wkz): 요약 블록 + 섹션 제목·행 자리.
function DetailSkeleton() {
  return (
    <View className="gap-10 px-6 pt-2" accessible accessibilityLabel="불러오는 중">
      <View className="gap-3">
        <Skeleton className="h-11 w-48 rounded-lg" />
        <Skeleton className="h-5 w-28 rounded-sm" />
        <Skeleton className="h-11 w-44 rounded-sm" />
        <Skeleton className="h-16 w-full rounded-lg" />
      </View>
      {SKELETON_SECTIONS.map((section) => (
        <View key={section.id} className="gap-3">
          <Skeleton className="h-6 w-28 rounded-sm" />
          {section.rows.map((row) => (
            <Skeleton key={row} className="h-14 w-full rounded-md" />
          ))}
        </View>
      ))}
    </View>
  );
}

export { CardBillingDetailScreen };
