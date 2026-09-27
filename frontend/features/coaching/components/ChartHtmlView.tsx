import { WebView, type WebViewNavigation } from "react-native-webview";

export type ChartHtmlViewProps = {
  /** 백엔드가 중계한 자기완결 차트 HTML(script·style 인라인, 외부 요청 없음). 앱이 만든 문자열을 넣지 않는다(규칙 50) */
  html: string;
  onLoadError: () => void;
};

const WEBVIEW_STYLE = { flex: 1 } as const;
/** 인라인 HTML 의 origin 은 about:blank 라 기본 화이트리스트(http·https)로는 빈 화면이 된다. 대신 아래 onShouldStartLoadWithRequest 로 바깥 이동을 막는다 */
const ORIGIN_WHITELIST = ["*"];

function isInlineDocument(request: WebViewNavigation): boolean {
  return request.url.startsWith("about:") || request.url.startsWith("data:");
}

/**
 * 예산 예측 차트 HTML 을 그리는 WebView(네이티브). 웹 빌드는 ChartHtmlView.web.tsx 의 iframe 이 맡는다.
 * 차트 페이지에 링크는 없지만, 있더라도 WebView 안에서 다른 주소로 가지 않게 한다.
 */
function ChartHtmlView({ html, onLoadError }: ChartHtmlViewProps) {
  return (
    <WebView
      source={{ html }}
      style={WEBVIEW_STYLE}
      originWhitelist={ORIGIN_WHITELIST}
      onShouldStartLoadWithRequest={isInlineDocument}
      setSupportMultipleWindows={false}
      allowsLinkPreview={false}
      domStorageEnabled={false}
      overScrollMode="never"
      onError={onLoadError}
      accessibilityLabel="예산 예측 차트"
    />
  );
}

export { ChartHtmlView };
