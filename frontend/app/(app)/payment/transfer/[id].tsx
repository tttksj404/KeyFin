import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { TransferApprovalScreen } from "@/features/payment/components/TransferApprovalScreen";
import { parseTransferId } from "@/features/payment/model";

// PAGE-25 이체 승인. 07:00 TRANSFER_REQUEST 푸시(refId=이체 id)의 진입점이다.
export default function TransferApprovalRoute() {
  const { id } = useLocalSearchParams();

  return (
    <View className="flex-1 bg-background">
      <TransferApprovalScreen transferId={parseTransferId(id)} />
    </View>
  );
}
