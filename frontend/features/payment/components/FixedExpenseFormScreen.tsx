import { useRouter } from "expo-router";
import { CalendarClock, Check, CircleAlert, Lock, Trash2, WifiOff } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";

import { AmountInput } from "@/components/ui/amount-input";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { KeyboardAvoidingView } from "@/components/ui/keyboard-avoiding-view";
import { Skeleton } from "@/components/ui/skeleton";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useAccounts } from "@/features/account/api/queries";
import type { LinkedAccount } from "@/features/account/model";
import {
  useCreateFixedExpense,
  useDeleteFixedExpense,
  useFixedExpense,
  useUpdateFixedExpense,
} from "@/features/payment/api/queries";
import { MANUAL_EXPENSE_TYPE_OPTIONS, expenseTypeIcon, expenseTypeLabel } from "@/features/payment/catalog";
import { SubscriptionCardField } from "@/features/payment/components/SubscriptionCardField";
import { fixedExpenseDeleteErrorMessage, fixedExpenseSaveErrorMessage } from "@/features/payment/errors";
import {
  EMPTY_FIXED_EXPENSE_FORM,
  MAX_FIXED_EXPENSE_NAME_LENGTH,
  MAX_PAYMENT_DAY,
  MIN_PAYMENT_DAY,
  fixedExpenseFormError,
  isVariableExpenseType,
  paymentDayLabel,
  toFixedExpenseForm,
  toFixedExpenseRequest,
  type FixedExpense,
  type FixedExpenseForm,
  type FixedExpenseRoute,
} from "@/features/payment/model";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

const FIXED_EXPENSE_LIST_ROUTE = "/payment/fixed-expense";
const MISSING_ACCOUNT_MESSAGE = "저장된 출금 계좌가 연결 목록에 없어요. 출금 계좌를 다시 골라 주세요.";

type FixedExpenseFormScreenProps = {
  /** 라우트 파라미터에서 검증한 값. null 이면 주소가 잘못됐다 */
  route: FixedExpenseRoute;
};

/**
 * PAGE-26 고정지출 등록·수정 (FR-PAY-07). 이름·유형·금액·출금일(1~31)·출금 계좌를 받아
 * POST /fixed-expenses 또는 PUT /fixed-expenses/{id}(본문 전체 교체)로 보낸다. 삭제는 확인 다이얼로그를 거친다.
 * 수정은 단건 조회 API 가 없어 GET /fixed-expenses 목록에서 그 항목을 찾아 채운다(유형·변동 여부·말일 보정 전 출금일까지).
 * 금융망에서 동기화된 카드 정기결제는 수정·삭제가 409(PAY_002)라 폼 대신 읽기 전용 상세를 보여준다
 * (캘린더·관리 목록에서 다른 항목과 똑같이 눌러 들어온다, 사용자 결정 2026-09-15).
 * Pencil PAGE-26 고정지출 등록 (LpGnf) · 수정 (v5HKz) · 못 찾음 (fmksb) · 카드 정기결제 (kwEMQ). 불러오는 중·불러오기 오류 시안은 없다.
 */
function FixedExpenseFormScreen({ route }: FixedExpenseFormScreenProps) {
  const router = useRouter();
  const goBack = () => {
    if (router.canGoBack()) router.back();
    else router.replace(FIXED_EXPENSE_LIST_ROUTE);
  };
  const openList = () => router.replace(FIXED_EXPENSE_LIST_ROUTE);

  if (route === null) return <FixedExpenseNotFound onBack={goBack} onOpenList={openList} />;
  if (route.mode === "create") return <FixedExpenseEditor editId={null} initial={EMPTY_FIXED_EXPENSE_FORM} onDone={goBack} />;
  return <FixedExpenseEditLoader id={route.id} onBack={goBack} onOpenList={openList} />;
}

type FixedExpenseEditLoaderProps = {
  id: number;
  onBack: () => void;
  onOpenList: () => void;
};

function FixedExpenseEditLoader({ id, onBack, onOpenList }: FixedExpenseEditLoaderProps) {
  const query = useFixedExpense(id);
  // 저장·삭제에 성공하면 목록을 다시 받는다. 뒤로 가는 동안 '못 찾음'으로 바뀌어 깜빡이지 않게 처음 찾은 값으로 폼을 고정한다.
  const [loaded, setLoaded] = useState<FixedExpense | null>(null);
  if (loaded === null && query.data) setLoaded(query.data);
  const expense = loaded ?? query.data ?? null;

  if (expense === null) {
    if (query.isPending) return <FixedExpenseLoading onBack={onBack} />;
    if (query.isError) {
      return (
        <View className="flex-1 bg-background">
          <ScreenHeader title="고정지출 수정" onBack={onBack} />
          <EmptyState
            icon={WifiOff}
            title="고정지출을 불러오지 못했어요"
            description="연결 상태를 확인한 뒤 다시 시도해 주세요."
            action={{ label: "다시 시도", onPress: () => query.refetch(), disabled: query.isFetching }}
          />
        </View>
      );
    }
    return <FixedExpenseNotFound onBack={onBack} onOpenList={onOpenList} />;
  }

  // 동기화 항목은 삭제되지 않아 고정할 이유가 없고, 결제 카드 지정(-184)이 목록을 다시 받으면 바로 보여야 한다
  if (expense.synced) return <SyncedExpenseDetail expense={query.data ?? expense} onBack={onBack} />;

  return <FixedExpenseEditor editId={id} initial={toFixedExpenseForm(expense)} onDone={onBack} />;
}

type FixedExpenseEditorProps = {
  /** null 이면 등록 */
  editId: number | null;
  initial: FixedExpenseForm;
  onDone: () => void;
};

function FixedExpenseEditor({ editId, initial, onDone }: FixedExpenseEditorProps) {
  const accounts = useAccounts();
  const create = useCreateFixedExpense();
  const update = useUpdateFixedExpense();
  const remove = useDeleteFixedExpense();
  const [form, setForm] = useState<FixedExpenseForm>(initial);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const isEdit = editId !== null;
  // 저장해 둔 계좌가 연결 해제되면 서버가 거절한다(ACCOUNT_001·002). 보내기 전에 다시 고르게 한다.
  const accountMissing =
    accounts.data !== undefined &&
    form.withdrawalAccountId !== null &&
    !accounts.data.some((account) => account.accountId === form.withdrawalAccountId);
  const invalidReason = fixedExpenseFormError(form) ?? (accountMissing ? MISSING_ACCOUNT_MESSAGE : null);
  const isPending = create.isPending || update.isPending || remove.isPending;
  const saveError = create.error ?? update.error;
  const isVariable = isVariableExpenseType(form.expenseType);

  const patch = (next: Partial<FixedExpenseForm>) => {
    setForm((current) => ({ ...current, ...next }));
    // 고치기 시작하면 지난 저장 실패 문구는 더 이상 맞지 않는다
    if (saveError !== null) {
      create.reset();
      update.reset();
    }
  };

  const submit = () => {
    if (invalidReason !== null || isPending) return;
    const request = toFixedExpenseRequest(form);
    if (editId === null) create.mutate(request, { onSuccess: onDone });
    else update.mutate({ id: editId, request }, { onSuccess: onDone });
  };

  const confirmDelete = () => {
    if (editId === null) return;
    setDeleteOpen(false);
    remove.mutate(editId, { onSuccess: onDone });
  };

  return (
    <Screen>
    <KeyboardAvoidingView className="flex-1">
      <ScreenHeader title={isEdit ? "고정지출 수정" : "고정지출 등록"} onBack={onDone} />

      <ScreenScrollView contentContainerClassName="gap-6 px-6 pb-8" keyboardShouldPersistTaps="handled">
        <Field label="이름">
          <Input
            className="h-input rounded-lg"
            value={form.name}
            onChangeText={(name) => patch({ name })}
            placeholder="월세, 관리비, 통신비 …"
            accessibilityLabel="고정지출 이름"
            maxLength={MAX_FIXED_EXPENSE_NAME_LENGTH}
            editable={!isPending}
          />
        </Field>

        <Field label="유형">
          <View className="flex-row flex-wrap gap-2">
            {MANUAL_EXPENSE_TYPE_OPTIONS.map((option) => (
              <TypeChip
                key={option.type}
                label={option.label}
                selected={form.expenseType === option.type}
                disabled={isPending}
                onPress={() => patch({ expenseType: option.type })}
              />
            ))}
          </View>
          <Text className="text-caption text-card-foreground">카드 정기결제와 카드 대금은 카드사에서 자동으로 불러와요.</Text>
        </Field>

        <Field label={isVariable ? "예상 금액" : "금액"}>
          <AmountInput
            variant="field"
            className="h-input rounded-lg"
            value={form.amount}
            onChangeValue={(amount) => patch({ amount })}
            editable={!isPending}
          />
          {isVariable ? (
            <Text className="text-caption text-card-foreground">공과금은 달마다 금액이 달라 예상액으로 준비해 둬요.</Text>
          ) : null}
        </Field>

        <Field label="출금일">
          <View className="flex-row items-center gap-2">
            <Input
              className="h-input w-20 rounded-lg text-center"
              value={form.paymentDay}
              onChangeText={(raw) => patch({ paymentDay: raw.replace(/[^0-9]/g, "").slice(0, 2) })}
              keyboardType="number-pad"
              accessibilityLabel="출금일"
              editable={!isPending}
            />
            <Text className="text-body text-foreground">일</Text>
          </View>
          <Text className="text-caption text-card-foreground">
            {MIN_PAYMENT_DAY}~{MAX_PAYMENT_DAY} 중에 고르면 돼요. 29~31일은 그 날짜가 없는 달이면 말일에 나가요.
          </Text>
        </Field>

        <Field label="출금 계좌">
          <AccountPicker
            accounts={accounts.data}
            isPending={accounts.isPending}
            isError={accounts.isError}
            disabled={isPending}
            selectedId={form.withdrawalAccountId}
            onSelect={(withdrawalAccountId) => patch({ withdrawalAccountId })}
            onRetry={() => accounts.refetch()}
          />
        </Field>

        {isEdit ? (
          <Button
            variant="ghost"
            className="h-button-md rounded-lg"
            disabled={isPending}
            accessibilityLabel="고정지출 삭제"
            onPress={() => setDeleteOpen(true)}
          >
            <Icon as={Trash2} size={18} className="text-destructive" />
            <Text className="text-destructive">삭제</Text>
          </Button>
        ) : null}
      </ScreenScrollView>

      <View className="gap-2 px-6 pb-8 pt-2">
        {saveError === null ? null : <ErrorLine message={fixedExpenseSaveErrorMessage(saveError)} />}
        {remove.error === null ? null : <ErrorLine message={fixedExpenseDeleteErrorMessage(remove.error)} />}
        {invalidReason === null ? null : <Text className="text-caption text-card-foreground">{invalidReason}</Text>}
        <Button
          size="lg"
          className="h-button-lg rounded-lg"
          disabled={invalidReason !== null || isPending}
          accessibilityState={{ disabled: invalidReason !== null || isPending }}
          onPress={submit}
        >
          <Text>{isPending ? "저장하는 중" : isEdit ? "저장" : "등록"}</Text>
        </Button>
      </View>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-h3 text-foreground">이 고정지출을 삭제할까요?</DialogTitle>
            <DialogDescription className="text-body-sm text-card-foreground">
              앞으로의 결제 캘린더와 준비 이체 제안에서 빠져요. 지난 이체 기록은 그대로 남아요.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onPress={() => setDeleteOpen(false)}>
              <Text>그대로 둘게요</Text>
            </Button>
            <Button variant="destructive" onPress={confirmDelete}>
              <Text>삭제</Text>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </KeyboardAvoidingView>
    </Screen>
  );
}

/** 동기화 항목은 출금 계좌가 없고 카드 청구에 포함된다 */
const CARD_PAYMENT_ROUTE_LABEL = "카드 대금으로 함께 나가요";

// 동기화된 카드 정기결제의 읽기 전용 상세. 거래 상세(PAGE-21)처럼 금액을 가운데 크게 두고 나머지는 구분선 목록, 잠김 사유는 muted 띠.
function SyncedExpenseDetail({ expense, onBack }: { expense: FixedExpense; onBack: () => void }) {
  const amount = expense.amount === null ? "청구서 기준" : formatKRW(expense.amount);

  return (
    <Screen>
      <ScreenHeader title="카드 정기결제" onBack={onBack} />
      <ScreenScrollView contentContainerClassName="gap-6 px-6 pb-8">
        <View className="items-center gap-2" accessible accessibilityLabel={`${expense.name} ${amount}`}>
          <View className="h-12 w-12 items-center justify-center rounded-full bg-accent">
            <Icon as={expenseTypeIcon(expense.expenseType)} size={24} className="text-primary" />
          </View>
          <Text className="text-center text-label text-card-foreground" numberOfLines={2}>
            {expense.name}
          </Text>
          <Text className="text-amount-lg tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
            {amount}
          </Text>
        </View>
        <View>
          <DetailRow label="유형" value={expenseTypeLabel(expense.expenseType)} />
          <DetailRow label="출금일" value={paymentDayLabel(expense.paymentDay)} />
          <DetailRow label="결제 경로" value={CARD_PAYMENT_ROUTE_LABEL} />
          <SubscriptionCardField expense={expense} />
        </View>
        <View className="flex-row gap-2 rounded-lg bg-muted p-3.5">
          <Icon as={Lock} size={16} className="mt-0.5 text-card-foreground" />
          <Text className="shrink text-body-sm text-card-foreground">
            금액·출금일은 카드사에서 관리해 여기서 바꿀 수 없어요. 결제 카드만 지정할 수 있어요.
          </Text>
        </View>
      </ScreenScrollView>
    </Screen>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-row items-start justify-between gap-3 border-b border-border py-3.5">
      <Text className="text-caption text-card-foreground">{label}</Text>
      <Text className="shrink text-body-sm text-foreground">{value}</Text>
    </View>
  );
}

function ErrorLine({ message }: { message: string }) {
  return (
    <View className="flex-row items-center gap-1.5" accessibilityLiveRegion="polite">
      <Icon as={CircleAlert} size={16} className="text-destructive" />
      <Text className="shrink text-caption text-destructive">{message}</Text>
    </View>
  );
}

type FixedExpenseNotFoundProps = {
  onBack: () => void;
  onOpenList: () => void;
};

function FixedExpenseNotFound({ onBack, onOpenList }: FixedExpenseNotFoundProps) {
  return (
    <View className="flex-1 bg-background">
      <ScreenHeader title="고정지출" onBack={onBack} />
      <EmptyState
        icon={CalendarClock}
        title="고정지출을 찾을 수 없어요"
        description="이미 삭제됐을 수 있어요. 고정지출 관리에서 다시 확인해 주세요."
        action={{ label: "고정지출 관리", onPress: onOpenList }}
      />
    </View>
  );
}

const SKELETON_FIELDS = [1, 2, 3, 4];

function FixedExpenseLoading({ onBack }: { onBack: () => void }) {
  return (
    <View className="flex-1 bg-background">
      <ScreenHeader title="고정지출 수정" onBack={onBack} />
      <View className="gap-6 px-6" accessible accessibilityLabel="불러오는 중">
        {SKELETON_FIELDS.map((row) => (
          <Skeleton key={row} className="h-14 w-full rounded-lg" />
        ))}
      </View>
    </View>
  );
}

type FieldProps = {
  label: string;
  children: React.ReactNode;
};

function Field({ label, children }: FieldProps) {
  return (
    <View className="gap-2">
      <Text className="text-label text-card-foreground">{label}</Text>
      {children}
    </View>
  );
}

type TypeChipProps = {
  label: string;
  selected: boolean;
  disabled: boolean;
  onPress: () => void;
};

function TypeChip({ label, selected, disabled, onPress }: TypeChipProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected, disabled }}
      disabled={disabled}
      onPress={onPress}
      className={cn(
        "min-h-touch justify-center rounded-lg border px-4 active:opacity-70",
        selected ? "border-primary bg-accent" : "border-border bg-card",
        disabled && "opacity-50"
      )}
    >
      <Text className={cn("text-label", selected ? "text-primary" : "text-foreground")}>{label}</Text>
    </Pressable>
  );
}

type AccountPickerProps = {
  accounts: LinkedAccount[] | undefined;
  isPending: boolean;
  isError: boolean;
  disabled: boolean;
  selectedId: number | null;
  onSelect: (accountId: number) => void;
  onRetry: () => void;
};

// 출금 계좌는 GET /accounts 의 관리 대상 계좌뿐이다(서버도 관리 대상만 받는다). 계좌번호는 마스킹된 값만 보여준다 (규칙 80).
function AccountPicker({ accounts, isPending, isError, disabled, selectedId, onSelect, onRetry }: AccountPickerProps) {
  if (isPending) return <Skeleton className="h-14 w-full rounded-lg" />;
  if (isError || accounts === undefined) {
    return (
      <Pressable accessibilityRole="button" className="h-input justify-center" onPress={onRetry}>
        <Text className="text-label text-primary">계좌를 불러오지 못했어요. 다시 시도</Text>
      </Pressable>
    );
  }
  if (accounts.length === 0) {
    return <Text className="text-body-sm text-card-foreground">연결된 계좌가 없어요. 자산 탭에서 계좌를 먼저 연결해 주세요.</Text>;
  }

  return (
    <View className="gap-2">
      {accounts.map((account) => {
        const selected = account.accountId === selectedId;
        const name = account.alias ?? account.bankName;
        return (
          <Pressable
            key={account.accountId}
            accessibilityRole="button"
            accessibilityLabel={`${name} ${account.maskedNo}`}
            accessibilityState={{ selected, disabled }}
            disabled={disabled}
            onPress={() => onSelect(account.accountId)}
            className={cn(
              "min-h-touch flex-row items-center justify-between gap-3 rounded-lg border px-4 py-3 active:opacity-70",
              selected ? "border-primary bg-accent" : "border-border bg-card",
              disabled && "opacity-50"
            )}
          >
            <View className="flex-1">
              <Text className="text-label text-foreground" numberOfLines={1}>
                {name}
              </Text>
              <Text className="text-caption tabular-nums text-card-foreground">{account.maskedNo}</Text>
            </View>
            {selected ? <Icon as={Check} size={18} className="text-primary" /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

export { FixedExpenseFormScreen };
export type { FixedExpenseFormScreenProps };
