import { Image, View } from "react-native";

import { Text } from "@/components/ui/text";
import { bankInitial, bankLogo, bankLogoByName } from "@/features/link/bank-catalog";

/** 로고 PNG 는 원본 크기 인라인 style 이 className 을 이기므로 감싼 타일을 채우게 둔다 (웹 NativeWind) */
const LOGO_FILL = { width: "100%", height: "100%" } as const;

type BankLogoTileProps = {
  /** 카드에는 코드가 없어 이름으로만 찾는다 */
  bankCode?: string;
  name: string;
};

// 36 로고 타일. 코드 → 이름 순으로 로고를 찾고, 없으면 이름 첫 글자 타일로 대체한다.
// 계좌·카드 연결(PAGE-04)과 수입 계좌 지정(PAGE-05)이 함께 쓴다.
function BankLogoTile({ bankCode, name }: BankLogoTileProps) {
  const logo = (bankCode === undefined ? undefined : bankLogo(bankCode)) ?? bankLogoByName(name);

  return (
    <View className="h-9 w-9 items-center justify-center overflow-hidden rounded-full bg-accent">
      {logo === undefined ? (
        <Text className="text-label text-primary">{bankInitial(name)}</Text>
      ) : (
        <Image source={logo} style={LOGO_FILL} resizeMode="contain" accessible={false} />
      )}
    </View>
  );
}

export { BankLogoTile };
