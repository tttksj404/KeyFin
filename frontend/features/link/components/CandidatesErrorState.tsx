import { useRouter } from "expo-router";
import { Link2Off, WifiOff } from "lucide-react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { needsFinanceReconnect } from "@/features/link/errors";

const FINANCE_EMAIL_ROUTE = "/onboarding/finance-email";

type CandidatesErrorStateProps = {
  error: unknown;
  retrying: boolean;
  onRetry: () => void;
};

// Pencil error (U9gpA). 금융망 연결이 끊긴 오류(LINK_002·FINANCE_005)는 다시 시도해도 같으므로
// 금융망 이메일 연결(PAGE-03B)로 보낸다. 연결에 성공하면 PAGE-03B 가 계좌·카드 연결(PAGE-04)로 돌려보낸다.
function CandidatesErrorState({ error, retrying, onRetry }: CandidatesErrorStateProps) {
  const router = useRouter();

  if (needsFinanceReconnect(error)) {
    return (
      <EmptyState
        icon={Link2Off}
        title="금융망에 다시 연결해 주세요"
        description="금융망 연결이 확인되지 않아 자산을 불러올 수 없어요."
        action={{ label: "금융망 연결하기", onPress: () => router.replace(FINANCE_EMAIL_ROUTE) }}
      />
    );
  }

  return (
    <EmptyState
      icon={WifiOff}
      title="자산을 불러오지 못했어요"
      description="연결 상태를 확인한 뒤 다시 시도해 주세요."
      action={{ label: "다시 시도", onPress: onRetry, disabled: retrying }}
    />
  );
}

export { CandidatesErrorState };
