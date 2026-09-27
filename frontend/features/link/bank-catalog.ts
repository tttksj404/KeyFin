/**
 * 은행 코드 → 로고. 코드·이름 목록은 SSAFY 금융망 기준이고(사용자 제공 2026-09-10),
 * 로고는 design.pen 아이콘(vnfzl)의 80x80 심볼을 3배 PNG 로 내보낸 것이다.
 *
 * 화면에 쓰는 이름은 서버가 주는 bankName 이다. 여기 이름은 로고가 없을 때의 폴백과 대조용이다.
 */
export type Bank = { code: string; name: string; logo?: number };

const LOGOS = {
  kdb: require("@/assets/brand/banks/kdb.png"),
  ibk: require("@/assets/brand/banks/ibk.png"),
  kb: require("@/assets/brand/banks/kb.png"),
  nh: require("@/assets/brand/banks/nh.png"),
  woori: require("@/assets/brand/banks/woori.png"),
  sc: require("@/assets/brand/banks/sc.png"),
  citi: require("@/assets/brand/banks/citi.png"),
  im: require("@/assets/brand/banks/im.png"),
  gwangjuJeonbuk: require("@/assets/brand/banks/gwangju-jeonbuk.png"),
  shinhanJeju: require("@/assets/brand/banks/shinhan-jeju.png"),
  gyeongnamBusan: require("@/assets/brand/banks/gyeongnam-busan.png"),
  mg: require("@/assets/brand/banks/mg.png"),
  hana: require("@/assets/brand/banks/hana.png"),
  kakao: require("@/assets/brand/banks/kakao.png"),
};

/**
 * 은행이 없는 카드 발급사 로고 (사용자 제공 PNG, 2026-09-23 삼성카드). 은행 로고와 달리 코드가 없어 이름으로만 찾는다.
 * 신한·국민·하나처럼 같은 브랜드 은행이 있는 카드사는 여기 두지 않고 은행 로고를 같이 쓴다.
 */
export const CARD_ISSUER_CATALOG: readonly { name: string; logo: number }[] = [
  { name: "삼성카드", logo: require("@/assets/brand/cards/samsung.png") },
];

/** 킷에서 두 은행이 한 심볼을 같이 쓰는 경우가 있다(광주·전북, 신한·제주, 경남·부산). */
export const BANK_CATALOG: readonly Bank[] = [
  { code: "001", name: "한국은행" },
  { code: "002", name: "산업은행", logo: LOGOS.kdb },
  { code: "003", name: "기업은행", logo: LOGOS.ibk },
  { code: "004", name: "국민은행", logo: LOGOS.kb },
  { code: "011", name: "농협은행", logo: LOGOS.nh },
  { code: "020", name: "우리은행", logo: LOGOS.woori },
  { code: "023", name: "SC제일은행", logo: LOGOS.sc },
  { code: "027", name: "시티은행", logo: LOGOS.citi },
  { code: "032", name: "대구은행", logo: LOGOS.im },
  { code: "034", name: "광주은행", logo: LOGOS.gwangjuJeonbuk },
  { code: "035", name: "제주은행", logo: LOGOS.shinhanJeju },
  { code: "037", name: "전북은행", logo: LOGOS.gwangjuJeonbuk },
  { code: "039", name: "경남은행", logo: LOGOS.gyeongnamBusan },
  { code: "045", name: "새마을금고", logo: LOGOS.mg },
  { code: "081", name: "KEB하나은행", logo: LOGOS.hana },
  { code: "088", name: "신한은행", logo: LOGOS.shinhanJeju },
  { code: "090", name: "카카오뱅크", logo: LOGOS.kakao },
  { code: "999", name: "싸피은행" },
];

const BY_CODE = new Map(BANK_CATALOG.map((bank) => [bank.code, bank]));

export function bankLogo(bankCode: string): number | undefined {
  return BY_CODE.get(bankCode)?.logo;
}

/**
 * 이름으로 로고를 찾는다. 카드 후보에는 은행 코드가 없고 발급사 이름만 오기 때문이다
 * ("신한카드" → 신한은행 로고, "삼성카드" → 카드사 로고). 계좌도 모르는 코드일 때 이름으로 한 번 더 찾는다.
 */
export function bankLogoByName(name: string): number | undefined {
  const key = brandKey(name);
  if (key.length === 0) return undefined;

  const matches = (catalogName: string) => {
    const catalogKey = brandKey(catalogName);
    return catalogKey.length > 0 && (key.includes(catalogKey) || catalogKey.includes(key));
  };

  return CARD_ISSUER_CATALOG.find((issuer) => matches(issuer.name))?.logo ?? BANK_CATALOG.find((bank) => matches(bank.name))?.logo;
}

/** 업권 접미사를 떼어 "신한카드"·"KEB하나은행" 처럼 다르게 적힌 같은 브랜드를 맞춘다 */
function brandKey(name: string): string {
  return name.replace(/[\s()]/g, "").replace(/(카드|은행|뱅크|금고|저축)/g, "");
}

/** 로고가 없는 은행(한국은행·싸피은행·목록에 없는 코드)의 폴백 타일 글자 */
export function bankInitial(bankName: string): string {
  return bankName.trim().charAt(0) || "은";
}
