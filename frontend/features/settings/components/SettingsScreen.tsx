import { useRouter } from "expo-router";
import { Check, CircleAlert } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";

import { AmountInput } from "@/components/ui/amount-input";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { KeyboardAvoidingView } from "@/components/ui/keyboard-avoiding-view";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Text } from "@/components/ui/text";
import {
  useCoachPersona,
  useNotificationSettings,
  useTransferSettings,
  useUpdateCoachPersona,
  useUpdateNotificationSettings,
  useUpdateTransferSettings,
} from "@/features/settings/api/queries";
import { coachPersonaLabel, notificationLabel, QUIET_HOUR_OPTIONS } from "@/features/settings/catalog";
import { coachPersonaErrorMessage, notificationSettingsErrorMessage, transferSettingsErrorMessage } from "@/features/settings/errors";
import {
  COACH_PERSONAS,
  isSettingsDirty,
  NOTIFICATION_KINDS,
  quietHoursError,
  settingsFormError,
  toSettingsForm,
  toTransferSettingsRequest,
  withNotificationKind,
  withQuietHours,
  type CoachPersona,
  type NotificationKind,
  type NotificationSettings,
  type QuietHours,
  type TransferSettings,
  type TransferSettingsForm,
} from "@/features/settings/model";
import { FilterSelect, type SelectOption } from "@/features/transaction/components/FilterSelect";
import { cn } from "@/lib/utils";

const MY_ROUTE = "/my";
/** 방해 금지를 처음 켤 때 보여 줄 범위 */
const DEFAULT_QUIET_HOURS: QuietHours = { start: "23:00", end: "08:00" };
const TIME_OPTIONS: SelectOption[] = QUIET_HOUR_OPTIONS.map((time) => ({ key: time, label: time }));

/**
 * PAGE-27 설정 상세. 이체 동의·한도(FR-PAY-04, P0), 알림 유형·방해 금지(FR-NTF-03, P1), 코치 말투(P1)를 한 화면에 둔다.
 * 세 구역이 서로 다른 조회라 각자 자기 자리에서 불러오고 실패한다 — 하나가 실패해도 나머지는 쓸 수 있다 (규칙 50).
 * 이체 설정만 저장 버튼을 두고(돈이 움직이는 값이라 확인 뒤 보낸다), 알림·코치는 누르는 즉시 저장한다.
 * Pencil 시안 없음 — design/DESIGN.md 의 섹션·카드 규칙을 따랐다.
 */
function SettingsScreen() {
  const router = useRouter();

  return (
    <Screen>
      <ScreenHeader title="설정" onBack={() => (router.canGoBack() ? router.back() : router.replace(MY_ROUTE))} />

      {/* 이체 한도 금액 입력이 있어 키패드가 덮지 않게 밀어 올린다 */}
      <KeyboardAvoidingView className="flex-1">
        <ScreenScrollView contentContainerClassName="gap-10 px-6 pb-8" keyboardShouldPersistTaps="handled">
          <TransferSection />
          <NotificationSection />
          <CoachSection />
        </ScreenScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <Text className="text-h2 text-foreground" accessibilityRole="header">
      {title}
    </Text>
  );
}

function SectionError({ message, onRetry, retrying }: { message: string; onRetry?: () => void; retrying?: boolean }) {
  return (
    <View className="flex-row items-center gap-1.5" accessibilityLiveRegion="polite">
      <Icon as={CircleAlert} size={16} className="text-destructive" />
      <Text className="shrink text-caption text-destructive">{message}</Text>
      {onRetry === undefined ? null : (
        <Pressable accessibilityRole="button" accessibilityState={{ disabled: retrying }} disabled={retrying} hitSlop={10} onPress={onRetry}>
          <Text className={cn("text-caption", retrying ? "text-card-foreground" : "text-primary")}>다시 시도</Text>
        </Pressable>
      )}
    </View>
  );
}

/* ───────────── 이체 ───────────── */

function TransferSection() {
  const settings = useTransferSettings();

  return (
    <View className="gap-3">
      <SectionTitle title="이체" />
      {settings.isPending ? (
        <SectionSkeleton rows={3} />
      ) : settings.data === undefined ? (
        <SectionError message="이체 설정을 불러오지 못했어요." onRetry={() => settings.refetch()} retrying={settings.isFetching} />
      ) : (
        <TransferForm settings={settings.data} />
      )}
    </View>
  );
}

function TransferForm({ settings }: { settings: TransferSettings }) {
  const update = useUpdateTransferSettings();
  const [form, setForm] = useState<TransferSettingsForm>(() => toSettingsForm(settings));

  const invalidReason = settingsFormError(form);
  const dirty = isSettingsDirty(form, settings);
  const canSave = dirty && invalidReason === null && !update.isPending;

  const patch = (next: Partial<TransferSettingsForm>) => setForm((current) => ({ ...current, ...next }));

  const save = () => {
    if (!canSave) return;
    update.mutate(toTransferSettingsRequest(form, settings), { onSuccess: (saved) => setForm(toSettingsForm(saved)) });
  };

  return (
    <View className="gap-4">
      {/* Pencil PAGE-27 설정 (WGeTO) 의 Card / Consent: 흰 카드 안에 동의 스위치와 설명 (2026-09-17) */}
      <View className="gap-3 rounded-2xl bg-card p-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
        <View className="flex-row items-center justify-between gap-3">
          <Text className="shrink text-h3 text-foreground">결제 준비 이체 동의</Text>
          <Switch
            value={form.consent}
            onValueChange={(consent) => patch({ consent })}
            disabled={update.isPending}
            accessibilityLabel="결제 준비 이체 동의"
          />
        </View>
        <Text className="text-body-sm text-card-foreground">
          동의하면 결제일 전에 부족한 금액을 미리 옮길지 물어봐요. 옮기는 건 매번 직접 승인해야 해요.
        </Text>
        {form.consent ? null : (
          <Text className="text-caption text-card-foreground">동의를 끄면 준비 이체 제안과 실행이 모두 멈춰요.</Text>
        )}
      </View>

      <LimitField
        label="1회 한도"
        value={form.limitOnce}
        editable={form.consent && !update.isPending}
        onChange={(limitOnce) => patch({ limitOnce })}
      />
      <LimitField
        label="1일 한도"
        value={form.limitDaily}
        editable={form.consent && !update.isPending}
        onChange={(limitDaily) => patch({ limitDaily })}
      />
      <Text className="text-caption text-card-foreground">
        한도를 넘는 이체는 승인해도 서버가 막아요. 한도는 준비 이체에만 쓰이고 직접 하는 송금과는 관계없어요.
      </Text>

      {update.isError ? <SectionError message={transferSettingsErrorMessage(update.error)} /> : null}
      {invalidReason === null ? null : <Text className="text-caption text-card-foreground">{invalidReason}</Text>}
      <Button
        size="lg"
        className="h-button-lg rounded-lg"
        disabled={!canSave}
        accessibilityState={{ disabled: !canSave }}
        accessibilityLabel="이체 설정 저장"
        onPress={save}
      >
        <Text>{update.isPending ? "저장하는 중" : "이체 설정 저장"}</Text>
      </Button>
    </View>
  );
}

type LimitFieldProps = {
  label: string;
  value: string;
  editable: boolean;
  onChange: (value: string) => void;
};

function LimitField({ label, value, editable, onChange }: LimitFieldProps) {
  return (
    <View className="gap-2">
      <Text className="text-label text-foreground">{label}</Text>
      <AmountInput
        variant="field"
        className="h-input rounded-lg"
        value={value}
        onChangeValue={onChange}
        editable={editable}
        accessibilityLabel={label}
      />
    </View>
  );
}

/* ───────────── 알림 ───────────── */

function NotificationSection() {
  const settings = useNotificationSettings();
  const update = useUpdateNotificationSettings();

  return (
    <View className="gap-3">
      <SectionTitle title="알림" />
      {settings.isPending ? (
        <SectionSkeleton rows={4} />
      ) : settings.data === undefined ? (
        <SectionError message="알림 설정을 불러오지 못했어요." onRetry={() => settings.refetch()} retrying={settings.isFetching} />
      ) : (
        <NotificationForm
          settings={settings.data}
          pending={update.isPending}
          errorMessage={update.isError ? notificationSettingsErrorMessage(update.error) : null}
          onChange={(next) => update.mutate(next)}
        />
      )}
    </View>
  );
}

type NotificationFormProps = {
  settings: NotificationSettings;
  pending: boolean;
  errorMessage: string | null;
  onChange: (next: NotificationSettings) => void;
};

// 토글·시간은 누르는 즉시 저장한다. 서버에 부분 수정이 없어 바뀐 설정 전체를 보낸다.
function NotificationForm({ settings, pending, errorMessage, onChange }: NotificationFormProps) {
  const quietHours = settings.quietHours;
  const rangeError = quietHoursError(quietHours);

  const changeQuietHours = (next: QuietHours | null) => {
    if (quietHoursError(next) !== null) return;
    onChange(withQuietHours(settings, next));
  };

  return (
    <View className="gap-4">
      <View className="gap-1 rounded-2xl bg-card px-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
        {NOTIFICATION_KINDS.map((kind, index) => (
          <NotificationToggle
            key={kind}
            kind={kind}
            value={settings.enabled[kind]}
            disabled={pending}
            last={index === NOTIFICATION_KINDS.length - 1}
            onChange={(enabled) => onChange(withNotificationKind(settings, kind, enabled))}
          />
        ))}
      </View>

      <View className="gap-3">
        <View className="flex-row items-center justify-between gap-3">
          <Text className="shrink text-label text-foreground">방해 금지 시간</Text>
          <Switch
            value={quietHours !== null}
            onValueChange={(on) => changeQuietHours(on ? DEFAULT_QUIET_HOURS : null)}
            disabled={pending}
            accessibilityLabel="방해 금지 시간"
          />
        </View>
        {quietHours === null ? (
          <Text className="text-caption text-card-foreground">켜면 그 시간에는 알림이 오지 않아요.</Text>
        ) : (
          <>
            <View className="flex-row items-center gap-2">
              <FilterSelect
                title="시작 시각"
                options={TIME_OPTIONS}
                selectedKey={quietHours.start}
                disabled={pending}
                onSelect={(start) => changeQuietHours({ ...quietHours, start })}
              />
              <Text className="text-body-sm text-card-foreground">부터</Text>
              <FilterSelect
                title="종료 시각"
                options={TIME_OPTIONS}
                selectedKey={quietHours.end}
                disabled={pending}
                onSelect={(end) => changeQuietHours({ ...quietHours, end })}
              />
              <Text className="text-body-sm text-card-foreground">까지</Text>
            </View>
            <Text className="text-caption text-card-foreground">
              자정을 지나는 범위도 괜찮아요. 이 시간에 온 알림은 소리 없이 쌓여 알림함에서 볼 수 있어요.
            </Text>
          </>
        )}
        {rangeError === null ? null : <Text className="text-caption text-card-foreground">{rangeError}</Text>}
      </View>

      {errorMessage === null ? null : <SectionError message={errorMessage} />}
    </View>
  );
}

type NotificationToggleProps = {
  kind: NotificationKind;
  value: boolean;
  disabled: boolean;
  /** 마지막 줄은 아래 선을 긋지 않는다 (RN 에는 :last-child 가 없다) */
  last: boolean;
  onChange: (enabled: boolean) => void;
};

function NotificationToggle({ kind, value, disabled, last, onChange }: NotificationToggleProps) {
  const { title, description } = notificationLabel(kind);

  return (
    <View className={cn("flex-row items-center justify-between gap-3 py-4", last ? null : "border-b border-border")}>
      <View className="shrink gap-0.5">
        <Text className="text-body text-foreground">{title}</Text>
        <Text className="text-caption text-card-foreground">{description}</Text>
      </View>
      <Switch value={value} onValueChange={onChange} disabled={disabled} accessibilityLabel={title} />
    </View>
  );
}

/* ───────────── 코치 말투 ───────────── */

function CoachSection() {
  const persona = useCoachPersona();
  const update = useUpdateCoachPersona();

  return (
    <View className="gap-3">
      <SectionTitle title="코치 말투" />
      <Text className="text-body-sm text-card-foreground">코치가 한마디 할 때 쓰는 말투예요.</Text>
      {persona.isPending ? (
        <SectionSkeleton rows={2} />
      ) : persona.data === undefined ? (
        <SectionError message="코치 말투를 불러오지 못했어요." onRetry={() => persona.refetch()} retrying={persona.isFetching} />
      ) : (
        <View className="gap-1 rounded-2xl bg-card px-5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none">
          {COACH_PERSONAS.map((option, index) => (
            <PersonaRow
              key={option}
              persona={option}
              selected={option === persona.data}
              disabled={update.isPending}
              last={index === COACH_PERSONAS.length - 1}
              onPress={() => option !== persona.data && update.mutate(option)}
            />
          ))}
        </View>
      )}
      {update.isError ? <SectionError message={coachPersonaErrorMessage(update.error)} /> : null}
    </View>
  );
}

type PersonaRowProps = {
  persona: CoachPersona;
  selected: boolean;
  disabled: boolean;
  last: boolean;
  onPress: () => void;
};

function PersonaRow({ persona, selected, disabled, last, onPress }: PersonaRowProps) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected, disabled }}
      accessibilityLabel={coachPersonaLabel(persona)}
      disabled={disabled}
      onPress={onPress}
      className={cn("h-touch flex-row items-center justify-between gap-3", last ? null : "border-b border-border", disabled && "opacity-60")}
    >
      <Text className={cn("shrink text-body", selected ? "text-primary" : "text-foreground")}>{coachPersonaLabel(persona)}</Text>
      {selected ? <Icon as={Check} size={18} className="text-primary" /> : null}
    </Pressable>
  );
}

function SectionSkeleton({ rows }: { rows: number }) {
  return (
    <View className="gap-3" accessible accessibilityLabel="불러오는 중">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-14 w-full rounded-lg" />
      ))}
    </View>
  );
}

export { SettingsScreen };
