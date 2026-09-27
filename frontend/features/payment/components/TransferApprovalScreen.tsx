import { useRouter } from "expo-router";
import { ArrowDown, Ban, CalendarClock, CircleAlert, CircleCheck, ShieldOff, WifiOff } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useAccounts } from "@/features/account/api/queries";
import type { LinkedAccount } from "@/features/account/model";
import { useApproveTransfer, usePostponeTransfer, useTransfer } from "@/features/payment/api/queries";
import {
  isIncomeAccountError,
  isRetryableTransferError,
  isStaleTransferError,
  isTransferSettingsError,
  isUnconfirmedTransferError,
  transferApproveErrorMessage,
  transferPostponeErrorMessage,
} from "@/features/payment/errors";
import {
  canApproveTransfer,
  canPostponeTransfer,
  transferHistoryLabel,
  transferStatusLabel,
  type Transfer,
  type TransferHistoryAction,
  type TransferHistoryEntry,
} from "@/features/payment/model";
import { useTransferSettings } from "@/features/settings/api/queries";
import { formatDateTime, formatMonthDay, parseKSTDateKey, parseKSTLocalDateTime } from "@/lib/date";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

const CALENDAR_ROUTE = "/payment/calendar";
const SETTINGS_ROUTE = "/my/settings";
/** 안전장치 ④(PAY_010)는 이체 설정이 아니라 수입 계좌 지정에서 고친다 (2026-09-16) */
const INCOME_ACCOUNT_ROUTE = "/account/income";
const HOME_ROUTE = "/";

type TransferApprovalScreenProps = {
  /** 라우트 파라미터에서 검증한 이체 제안 id. 형식이 틀리면 null */
  transferId: number | null;
};

/**
 * PAGE-25 이체 승인 (FR-PAY-03·04). 07:00 TRANSFER_REQUEST 푸시의 진입점이다.
 * 규칙 80: 동의가 꺼져 있으면 실행 경로를 아예 열지 않고, 승인은 확인 다이얼로그를 거치며,
 * 요청 중에는 버튼을 잠가 같은 제안 id 로 두 번 보내지 않는다. 자동 재시도는 하지 않고
 * 네트워크 오류로 결과를 모를 때는 서버 상태(GET /transfers)로 확정한다. Pencil 시안 없음.
 */
function TransferApprovalScreen({ transferId }: TransferApprovalScreenProps) {
  const router = useRouter();
  const settings = useTransferSettings();
  // 단건 조회(GET /transfers/{id}, -62). 목록 첫 쪽에 없는 제안도 딥링크·푸시로 열린다. id 가 틀리면 조회하지 않는다.
  const detail = useTransfer(transferId);
  const accounts = useAccounts();
  const approve = useApproveTransfer();
  const postpone = usePostponeTransfer();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const transfer = detail.data?.transfer ?? null;
  const loading = transferId !== null && detail.isPending;
  // 404(PAY_005)는 "없는 제안" 이라 빈 상태로, 그 밖의 실패만 연결 오류로 보여 준다
  const unreachable = detail.isError && !isStaleTransferError(detail.error);
  const isPending = approve.isPending || postpone.isPending;

  const goBack = () => {
    if (router.canGoBack()) router.back();
    else router.replace(HOME_ROUTE);
  };

  const refresh = () => {
    void detail.refetch();
  };

  const openSettings = () => router.push(SETTINGS_ROUTE);
  const openIncomeAccount = () => router.push(INCOME_ACCOUNT_ROUTE);

  const runApprove = () => {
    if (transfer === null || isPending) return;
    setConfirmOpen(false);
    approve.mutate(transfer.id);
  };

  const runPostpone = () => {
    if (transfer === null || isPending) return;
    postpone.mutate(transfer.id, { onSuccess: goBack });
  };

  return (
    <Screen>
      <ScreenHeader title="이체 승인" onBack={goBack} />

      {settings.isPending || loading ? (
        <ApprovalSkeleton />
      ) : settings.data?.consent === false ? (
        <EmptyState
          icon={ShieldOff}
          title="이체 동의가 꺼져 있어요"
          description="설정에서 결제 준비 이체에 동의하면 제안을 받을 수 있어요."
          action={{ label: "설정 열기", onPress: () => router.replace(SETTINGS_ROUTE) }}
        />
      ) : unreachable ? (
        <EmptyState
          icon={WifiOff}
          title="이체 제안을 불러오지 못했어요"
          description="연결 상태를 확인한 뒤 다시 시도해 주세요."
          action={{ label: "다시 시도", onPress: refresh, disabled: detail.isFetching }}
        />
      ) : transfer === null ? (
        <EmptyState
          icon={CalendarClock}
          title="준비할 결제가 없어요"
          description="결제일이 가까워지면 미리 옮길지 물어볼게요."
          action={{ label: "결제 캘린더", onPress: () => router.replace(CALENDAR_ROUTE) }}
        />
      ) : (
        <>
          <ScreenScrollView contentContainerClassName="gap-5 px-6 pb-8">
            <TransferSummary transfer={transfer} accounts={accounts.data} />
            {transfer.status === "PROPOSED" ? (
              <LimitNote once={settings.data?.limitOnce} daily={settings.data?.limitDaily} />
            ) : (
              <ResultCard transfer={transfer} />
            )}
            <HistoryTimeline history={detail.data?.history ?? []} />
          </ScreenScrollView>

          <View className="gap-2 px-6 pb-8 pt-2">
            {approve.isError ? (
              <ErrorLine
                message={transferApproveErrorMessage(approve.error)}
                action={approveErrorAction(approve.error, refresh, openSettings, openIncomeAccount)}
              />
            ) : null}
            {postpone.isError ? (
              <ErrorLine
                message={transferPostponeErrorMessage(postpone.error)}
                action={isStaleTransferError(postpone.error) ? { label: "상태 새로 고침", onPress: refresh } : null}
              />
            ) : null}

            {canApproveTransfer(transfer) ? (
              <Button
                size="lg"
                className="h-button-lg rounded-lg"
                disabled={isPending}
                accessibilityState={{ disabled: isPending }}
                accessibilityLabel={approveLabel(transfer)}
                onPress={() => setConfirmOpen(true)}
              >
                <Text>{approve.isPending ? "이체하는 중" : approveLabel(transfer)}</Text>
              </Button>
            ) : null}
            {canPostponeTransfer(transfer) ? (
              <Button
                variant="outline"
                className="h-button-md rounded-lg"
                disabled={isPending}
                accessibilityState={{ disabled: isPending }}
                accessibilityLabel="나중에"
                onPress={runPostpone}
              >
                <Text>{postpone.isPending ? "미루는 중" : "나중에"}</Text>
              </Button>
            ) : null}
            {canApproveTransfer(transfer) ? null : (
              <Button variant="secondary" className="h-button-lg rounded-lg" onPress={() => router.replace(CALENDAR_ROUTE)}>
                <Text>결제 캘린더 보기</Text>
              </Button>
            )}
          </View>

          <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="text-h3 text-foreground">{formatKRW(transfer.requiredAmount)}을 옮길까요?</DialogTitle>
                <DialogDescription className="text-body-sm text-card-foreground">
                  {accountLabel(accounts.data, transfer.fromAccountId)} → {accountLabel(accounts.data, transfer.toAccountId)}
                  {"\n"}
                  {formatMonthDay(parseKSTDateKey(transfer.dueDate))} {transfer.purposeName} 출금에 쓸 돈이에요.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onPress={() => setConfirmOpen(false)}>
                  <Text>취소</Text>
                </Button>
                <Button disabled={isPending} onPress={runApprove}>
                  <Text>이체하기</Text>
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </>
      )}
    </Screen>
  );
}

/**
 * 안전장치 ①~③(403 PAY_007~009)은 이체 설정을, ④(PAY_010)는 수입 계좌 지정을 고쳐야 풀린다.
 * 미확인·어긋남·금융망 장애는 서버 상태를 다시 받아야 다음 수가 보인다. 잔액 부족·은행 한도(422)는 제안이 FAILED 로 끝나 화면에서 할 일이 없다.
 */
function approveErrorAction(
  error: unknown,
  refresh: () => void,
  openSettings: () => void,
  openIncomeAccount: () => void
): ErrorLineProps["action"] {
  if (isTransferSettingsError(error)) return { label: "이체 설정 열기", onPress: openSettings };
  if (isIncomeAccountError(error)) return { label: "수입 계좌 변경", onPress: openIncomeAccount };
  if (isUnconfirmedTransferError(error) || isStaleTransferError(error) || isRetryableTransferError(error)) {
    return { label: "상태 새로 고침", onPress: refresh };
  }
  return null;
}

/** 실행 중(APPROVED)인 건의 승인은 같은 기관거래고유번호로 재시도하는 것이라 문구를 나눈다 */
function approveLabel(transfer: Transfer): string {
  return transfer.status === "APPROVED" ? "다시 시도" : "이체하기";
}

/** 계좌 이름은 GET /accounts 에서 찾고, 못 찾으면 id 만 보여준다. 계좌번호는 마스킹된 값뿐이다 (규칙 80) */
function accountLabel(accounts: LinkedAccount[] | undefined, accountId: number): string {
  const account = accounts?.find((item) => item.accountId === accountId);
  if (account === undefined) return `계좌 #${accountId}`;
  return `${account.alias ?? account.bankName} ${account.maskedNo}`;
}

type TransferSummaryProps = {
  transfer: Transfer;
  accounts: LinkedAccount[] | undefined;
};

// Pencil PAGE-25 이체 승인 (t1kTHP) 의 Card / Summary: 흰 카드 안에 출금일·목적 · 준비할 금액 · 계좌 흐름 (2026-09-17 사용자 결정 — o8TlhF 의 카드 없는 안에서 되돌림).
function TransferSummary({ transfer, accounts }: TransferSummaryProps) {
  return (
    <View className="gap-4 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
      <View className="gap-1">
        <Text className="text-caption text-card-foreground">
          {formatMonthDay(parseKSTDateKey(transfer.dueDate))} 출금 · {transfer.purposeName}
        </Text>
        <Text className="text-h2 text-foreground">준비할 금액</Text>
      </View>
      <Text className="text-amount-lg tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
        {formatKRW(transfer.requiredAmount)}
      </Text>
      <View className="gap-2">
        <AccountLine label="출금 계좌" value={accountLabel(accounts, transfer.fromAccountId)} />
        <Icon as={ArrowDown} size={16} className="text-card-foreground" />
        <AccountLine label="결제 계좌" value={accountLabel(accounts, transfer.toAccountId)} />
      </View>
    </View>
  );
}

type AccountLineProps = { label: string; value: string };

function AccountLine({ label, value }: AccountLineProps) {
  return (
    <View className="flex-row items-center justify-between gap-3">
      <Text className="text-caption text-card-foreground">{label}</Text>
      <Text className="shrink text-label tabular-nums text-foreground" numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

type LimitNoteProps = { once: string | null | undefined; daily: string | null | undefined };

// 한도는 서버가 실행 직전 검사한다. 화면은 지금 설정값을 알려주기만 하고 미설정(null)이면 적지 않는다 (FR-PAY-04).
function LimitNote({ once, daily }: LimitNoteProps) {
  if (once === undefined || once === null || daily === undefined || daily === null) return null;

  return (
    <Text className="text-caption tabular-nums text-card-foreground">
      1회 한도 {formatKRW(once)} · 1일 한도 {formatKRW(daily)} 안에서 실행돼요. 넘으면 서버가 막아요.
    </Text>
  );
}

type ResultCardProps = { transfer: Transfer };

// 결과는 서버 상태를 그대로 보여준다. 실패 사유도 서버 문구를 고치지 않는다 (명세 §5).
// 카드가 아니라 상태 색 띠다(금융망 이메일의 안내 띠와 같은 모양): 성공 positive-muted · 실패 destructive-muted · 그 외 muted.
function ResultCard({ transfer }: ResultCardProps) {
  const failed = transfer.status === "FAILED";
  const executed = transfer.status === "EXECUTED";

  return (
    <View
      className={cn(
        "gap-2 rounded-lg p-3.5",
        failed ? "bg-destructive-muted" : executed ? "bg-positive-muted" : "bg-muted"
      )}
    >
      <View className="flex-row items-center gap-2">
        <Icon
          as={failed ? CircleAlert : CircleCheck}
          size={20}
          className={failed ? "text-destructive" : executed ? "text-positive" : "text-card-foreground"}
        />
        <Text className="text-h3 text-foreground">{transferStatusLabel(transfer.status)}</Text>
      </View>
      {executed && transfer.executedAt !== null ? (
        <Text className="text-body-sm tabular-nums text-card-foreground">
          {formatDateTime(parseKSTLocalDateTime(transfer.executedAt))}에 옮겼어요.
        </Text>
      ) : null}
      {failed ? (
        <>
          <Text className="text-body-sm text-destructive">{transfer.failReason ?? "실패 사유를 받지 못했어요."}</Text>
          <Text className="text-caption text-card-foreground">
            결제일 전에 잔액을 채우면 다음 날 아침 8시 30분에 다시 제안해요. 급하면 직접 옮겨 주세요.
          </Text>
        </>
      ) : null}
      {transfer.status === "APPROVED" ? (
        <Text className="text-body-sm text-card-foreground">
          승인은 됐는데 결과를 받지 못했어요. 30분 안에 자동으로 다시 확인하고, [다시 시도] 를 눌러도 같은 건으로 확인해요 — 이미
          옮겨졌으면 두 번 나가지 않아요.
        </Text>
      ) : null}
      {transfer.status === "CANCELED" || transfer.status === "UNKNOWN" ? (
        <Text className="text-body-sm text-card-foreground">이 제안은 더 이상 실행되지 않아요.</Text>
      ) : null}
    </View>
  );
}

type HistoryTimelineProps = { history: TransferHistoryEntry[] };

/**
 * 감사 타임라인 (GET /transfers/{id} 의 history, 오래된 순). 돈이 움직인 기록이라 서버가 남긴 근거 문구를
 * 그대로 적고 화면에서 다시 쓰지 않는다 (규칙 80). 기록이 없는 제안(갓 만들어진 PROPOSED)은 아예 그리지 않는다.
 */
function HistoryTimeline({ history }: HistoryTimelineProps) {
  if (history.length === 0) return null;

  return (
    <View className="gap-3 rounded-lg bg-muted p-3.5">
      <Text className="text-label text-foreground">진행 기록</Text>
      {history.map((entry, index) => (
        <View key={`${entry.at}-${index}`} className="flex-row gap-2.5">
          <Icon as={historyIcon(entry.action)} size={16} className={cn("mt-0.5", historyTone(entry.action))} />
          <View className="shrink gap-0.5">
            <View className="flex-row items-center gap-2">
              <Text className="text-body-sm text-foreground">{transferHistoryLabel(entry.action)}</Text>
              <Text className="text-caption tabular-nums text-card-foreground">
                {formatDateTime(parseKSTLocalDateTime(entry.at))}
              </Text>
            </View>
            {entry.basis ? <Text className="text-caption text-card-foreground">{entry.basis}</Text> : null}
          </View>
        </View>
      ))}
    </View>
  );
}

function historyIcon(action: TransferHistoryAction) {
  if (action === "EXECUTE") return CircleCheck;
  if (action === "FAIL") return CircleAlert;
  if (action === "CANCEL") return Ban;
  return CalendarClock;
}

function historyTone(action: TransferHistoryAction): string {
  if (action === "EXECUTE") return "text-positive";
  if (action === "FAIL") return "text-destructive";
  return "text-card-foreground";
}

type ErrorLineProps = {
  message: string;
  action: { label: string; onPress: () => void } | null;
};

function ErrorLine({ message, action }: ErrorLineProps) {
  return (
    <View className="gap-1" accessibilityLiveRegion="polite">
      <View className="flex-row items-center gap-1.5">
        <Icon as={CircleAlert} size={16} className="text-destructive" />
        <Text className="shrink text-caption text-destructive">{message}</Text>
      </View>
      {action === null ? null : (
        <Pressable accessibilityRole="button" accessibilityLabel={action.label} hitSlop={8} onPress={action.onPress}>
          <Text className="text-caption text-primary">{action.label}</Text>
        </Pressable>
      )}
    </View>
  );
}

function ApprovalSkeleton() {
  return (
    <View className="gap-4 px-6 pt-3" accessible accessibilityLabel="불러오는 중">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-7 w-28" />
      <Skeleton className="h-11 w-48" />
      <Skeleton className="h-5 w-full" />
      <Skeleton className="h-5 w-full" />
      <Skeleton className="h-5 w-3/4" />
    </View>
  );
}

export { TransferApprovalScreen };
export type { TransferApprovalScreenProps };
