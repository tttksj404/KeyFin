import { useRouter } from "expo-router";
import { Circle, CircleDot, WalletMinimal, WifiOff } from "lucide-react-native";
import * as React from "react";
import { Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useAccounts, useSetIncomeAccount } from "@/features/account/api/queries";
import { incomeAccountErrorMessage } from "@/features/account/errors";
import { canSubmitIncomeAccount, incomeAccountIdOf, type IncomeAccountOption } from "@/features/account/model";
import { BankLogoTile } from "@/features/link/components/BankLogoTile";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

/** 다음은 소비 분석(PAGE-06 분석 중) */
const NEXT_ROUTE = "/onboarding/spending-analysis";

const ASSET_SELECT_ROUTE = "/onboarding/asset-select";

/** 하단 CTA 가 안전 영역이 없는 기기에서도 띄워지는 최소 여백 (AssetSelectScreen 과 같은 기준) */
const MIN_BOTTOM_INSET = 12;

/** 변경 모드에서 돌아갈 곳이 없을 때(딥링크) */
const ASSETS_ROUTE = "/assets";

type IncomeAccountScreenProps = {
  /**
   * onboarding = PAGE-05, 지정 뒤 소비 분석으로 넘어간다.
   * change = 자산 탭·이체 승인(PAY_010)에서 들어오는 변경 화면. 헤더에 뒤로가기가 있고 바꾼 뒤 돌아간다(2026-09-16).
   */
  mode?: "onboarding" | "change";
};

// PAGE-05 수입 계좌 지정. Pencil 시안이 없어 계좌·카드 연결(PAGE-04)의 구성과 행 모양을 따른다.
// 목록은 GET /accounts(관리 중 계좌)이고, 이미 수입 계좌가 있으면 그 계좌를 골라 둔 채로 보여 준다.
function IncomeAccountScreen({ mode = "onboarding" }: IncomeAccountScreenProps) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const accounts = useAccounts();
  const setIncomeAccount = useSetIncomeAccount();
  const changing = mode === "change";

  // 사용자가 고르기 전에는 서버의 현재 수입 계좌를 선택값으로 쓴다(파생값이라 state 에 복사하지 않는다).
  const [pickedId, setPickedId] = React.useState<number | null>(null);

  const options = accounts.data ?? [];
  const currentId = incomeAccountIdOf(options);
  const selectedId = pickedId ?? currentId;
  // 변경 모드에서 지금 수입 계좌를 그대로 고른 건 보낼 게 없다(서버도 멱등이라 200 이지만 헛요청이다)
  const unchanged = changing && selectedId === currentId;
  const canSubmit = canSubmitIncomeAccount(options, selectedId) && !unchanged && !setIncomeAccount.isPending;
  const errorMessage = setIncomeAccount.isError ? incomeAccountErrorMessage(setIncomeAccount.error) : null;

  const goBack = () => {
    if (router.canGoBack()) router.back();
    else router.replace(ASSETS_ROUTE);
  };

  const handleSubmit = () => {
    if (!canSubmit || selectedId === null) return;
    setIncomeAccount.mutate(selectedId, { onSuccess: () => (changing ? goBack() : router.replace(NEXT_ROUTE)) });
  };

  return (
    <Screen>
      {changing ? <ScreenHeader title="수입 계좌 변경" onBack={goBack} /> : null}
      {/* 온보딩에는 헤더가 없어 상태바 높이와 위 여백을 직접 둔다 — 헤더 통일 때 둘 다 빠져 제목이 맨 위에 붙었다 (2026-09-17) */}
      <View className="flex-1 gap-5 px-6" style={changing ? undefined : { paddingTop: insets.top + ONBOARDING_TOP_GAP }}>
        <View className="gap-1.5">
          <Text className="text-h2 text-foreground" accessibilityRole="header">
            수입이 들어오는 계좌를 골라 주세요
          </Text>
          <Text className="text-body-sm text-card-foreground">급여·용돈처럼 돈이 들어오는 계좌 1개를 지정해요.</Text>
        </View>

        {accounts.isPending ? (
          <OptionsSkeleton />
        ) : accounts.isError ? (
          <View className="flex-1 justify-center pb-20">
            <EmptyState
              icon={WifiOff}
              title="계좌를 불러오지 못했어요"
              description="연결 상태를 확인한 뒤 다시 시도해 주세요."
              action={{ label: "다시 시도", onPress: () => accounts.refetch(), disabled: accounts.isFetching }}
            />
          </View>
        ) : options.length === 0 ? (
          <View className="flex-1 justify-center pb-20">
            <EmptyState
              icon={WalletMinimal}
              title="연결된 계좌가 없어요"
              description="수입 계좌로 지정하려면 계좌를 먼저 연결해 주세요."
              action={{ label: "계좌 연결하기", onPress: () => (changing ? router.push(ASSET_SELECT_ROUTE) : router.replace(ASSET_SELECT_ROUTE)) }}
            />
          </View>
        ) : (
          <ScreenScrollView className="flex-1" contentContainerClassName="gap-2.5 pb-6" accessibilityRole="radiogroup">
            {options.map((option) => (
              <IncomeAccountRow
                key={option.accountId}
                option={option}
                selected={option.accountId === selectedId}
                disabled={setIncomeAccount.isPending}
                onSelect={() => setPickedId(option.accountId)}
              />
            ))}
          </ScreenScrollView>
        )}
      </View>

      <View className="gap-2 px-6 pt-3" style={{ paddingBottom: Math.max(insets.bottom, MIN_BOTTOM_INSET) }}>
        {errorMessage === null ? null : (
          <Text className="text-caption text-destructive" accessibilityLiveRegion="polite">
            {errorMessage}
          </Text>
        )}
        <Button size="lg" className="h-button-lg rounded-lg" onPress={handleSubmit} disabled={!canSubmit}>
          <Text>{setIncomeAccount.isPending ? "지정하는 중…" : changing ? "변경" : "다음"}</Text>
        </Button>
      </View>
    </Screen>
  );
}

/** 헤더 없는 온보딩 모드에서 상태바 아래 제목까지의 간격. 섹션 간격(40)과 같다 */
const ONBOARDING_TOP_GAP = 40;

type IncomeAccountRowProps = {
  option: IncomeAccountOption;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
};

// PAGE-04 행과 같은 모양(표시 + 36 로고 타일 + 이름/마스킹 번호 + 잔액)에 체크 대신 라디오를 둔다.
function IncomeAccountRow({ option, selected, disabled, onSelect }: IncomeAccountRowProps) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={`${option.bankName} ${option.maskedNo}`}
      accessibilityState={{ checked: selected, disabled }}
      disabled={disabled}
      onPress={onSelect}
      className={cn(
        "flex-row items-center gap-3 rounded-lg border bg-card px-4 py-3.5",
        selected ? "border-primary" : "border-border"
      )}
    >
      <Icon
        as={selected ? CircleDot : Circle}
        size={20}
        className={selected ? "text-primary" : "text-card-foreground"}
      />

      <BankLogoTile name={option.bankName} />

      <View className="flex-1 gap-0.5">
        <Text className="text-label text-foreground" numberOfLines={1}>
          {option.bankName}
        </Text>
        <Text className="text-caption tabular-nums text-card-foreground" numberOfLines={1}>
          {option.maskedNo}
        </Text>
      </View>

      <Text className="text-amount-sm tabular-nums text-foreground" maxFontSizeMultiplier={1.3}>
        {formatKRW(option.balance)}
      </Text>
    </Pressable>
  );
}

const SKELETON_ROWS = [1, 2];

function OptionsSkeleton() {
  return (
    <View className="gap-2.5" accessible accessibilityLabel="불러오는 중">
      {SKELETON_ROWS.map((row) => (
        <Skeleton key={row} className="h-16 w-full rounded-lg" />
      ))}
    </View>
  );
}

export { IncomeAccountScreen };
