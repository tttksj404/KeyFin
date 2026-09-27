import type { ChartHtmlViewProps } from "@/features/coaching/components/ChartHtmlView";

/** 부모 폭·높이를 채우고 테두리를 없앤다. 웹 iframe 이라 RN 스타일이 아니다 */
const IFRAME_STYLE = { border: 0, width: "100%", height: "100%", display: "block" } as const;

/**
 * 웹 빌드용 — react-native-webview 는 웹 구현이 없어 iframe 에 문자열을 직접 넣는다(srcdoc).
 * 차트 스크립트는 돌려야 하니 allow-scripts 만 열고 같은 출처 권한은 주지 않는다. AI 서버의 frame-ancestors 는 HTTP 헤더라
 * 문자열 삽입에는 걸리지 않는다.
 */
function ChartHtmlView({ html }: ChartHtmlViewProps) {
  return <iframe srcDoc={html} sandbox="allow-scripts" title="예산 예측 차트" style={IFRAME_STYLE} />;
}

export { ChartHtmlView };
