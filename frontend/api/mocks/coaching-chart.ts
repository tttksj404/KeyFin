/**
 * GET /coaching/charts/{chartId}/html 목 — AI 서버 `/v1/charts/{id}/html`(ai/coaching/vendor/keyfin_chart/forecast-template.html) 을
 * 백엔드가 중계해 주는 자기완결 HTML 의 축소판. 실제 페이지는 약 50KB(카테고리 사용률 차트·누적 소비 선·일별 막대·표)이고
 * script·style 이 전부 인라인이라 외부 요청이 없다. 여기서는 WebView 세팅 확인용으로 같은 구성을 작은 인라인 SVG 로 흉내 낸다.
 * 금액·기간은 계약 예시가 아직 없어 더미 값이다(2026-09-22, 중계 경로 TBD).
 */

/** AI 서버 차트 id 는 uuid4().hex(32자 16진수)다 */
export const MOCK_CHART_ID = "3f2a9c1e0b7d4e6f8a1b2c3d4e5f6a7b";

export const MOCK_CHART_HTML = `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KeyFin · 예산 기간별 소비 예측</title>
<style>
  :root { --ink: #1c1930; --muted: #716b80; --line: #e6e3f0; --brand: #5140a6; --tint: #f0edff; --warn: #a52c58; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 20px 20px 40px; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--ink); background: #fff; }
  h1 { font-size: 18px; margin: 0 0 6px; }
  h2 { font-size: 15px; margin: 24px 0 8px; }
  .period-tag { display: inline-block; background: var(--tint); color: var(--brand); padding: 8px 12px; border-radius: 8px; font-size: 12px; line-height: 1.6; }
  .row { display: flex; align-items: center; gap: 10px; margin: 10px 0; font-size: 13px; }
  .row .name { width: 52px; color: var(--muted); }
  .row .bar { flex: 1; height: 10px; background: var(--line); border-radius: 5px; overflow: hidden; }
  .row .bar i { display: block; height: 100%; background: var(--brand); }
  .row .bar i.over { background: var(--warn); }
  .row .pct { width: 44px; text-align: right; font-variant-numeric: tabular-nums; }
  .card { border: 1px solid var(--line); border-radius: 16px; padding: 16px; margin-top: 12px; }
  .total { font-size: 22px; font-weight: 700; margin: 4px 0; }
  .helper { font-size: 12px; color: var(--muted); line-height: 1.7; }
  svg { display: block; width: 100%; height: auto; }
  .note { margin-top: 16px; font-size: 13px; line-height: 1.8; }
  .source { color: var(--brand); font-weight: 600; }
</style>
</head>
<body>
<h1>예산 기간별 소비 예측</h1>
<span class="period-tag">2026-09-01 ~ 2026-09-30 · 기준일 2026-09-22</span>

<h2>카테고리별 예산 사용률</h2>
<div class="row"><span class="name">식비</span><div class="bar"><i style="width:72%"></i></div><span class="pct">72%</span></div>
<div class="row"><span class="name">외식</span><div class="bar"><i class="over" style="width:100%"></i></div><span class="pct">108%</span></div>
<div class="row"><span class="name">교통</span><div class="bar"><i style="width:41%"></i></div><span class="pct">41%</span></div>
<div class="row"><span class="name">쇼핑</span><div class="bar"><i style="width:63%"></i></div><span class="pct">63%</span></div>
<div class="row"><span class="name">문화</span><div class="bar"><i style="width:28%"></i></div><span class="pct">28%</span></div>
<div class="row"><span class="name">생활</span><div class="bar"><i style="width:55%"></i></div><span class="pct">55%</span></div>
<div class="row"><span class="name">기타</span><div class="bar"><i style="width:19%"></i></div><span class="pct">19%</span></div>

<div class="card">
  <h2 style="margin-top:0">소비 추이</h2>
  <div class="total">기간 말 예상 총소비 1,284,000원</div>
  <div class="helper">현재까지 873,500원 · 예산 1,200,000원 · 실선은 기록, 점선은 같은 시뮬레이션의 P50 경로</div>
  <svg viewBox="0 0 320 160" role="img" aria-label="누적 소비 선">
    <line x1="30" y1="130" x2="310" y2="130" stroke="#e6e3f0"/>
    <line x1="30" y1="40" x2="310" y2="40" stroke="#e6e3f0" stroke-dasharray="4 4"/>
    <text x="34" y="36" font-size="9" fill="#716b80">예산 1,200,000</text>
    <polyline fill="none" stroke="#5140a6" stroke-width="2.5" points="30,130 70,118 110,104 150,96 190,80 230,66"/>
    <polyline fill="none" stroke="#5140a6" stroke-width="2.5" stroke-dasharray="5 4" points="230,66 260,52 290,38 310,30"/>
    <circle cx="230" cy="66" r="3.5" fill="#5140a6"/>
    <text x="30" y="146" font-size="9" fill="#716b80">09/01</text>
    <text x="218" y="146" font-size="9" fill="#716b80">09/22</text>
    <text x="290" y="146" font-size="9" fill="#716b80">09/30</text>
  </svg>

  <h2>일별 소비</h2>
  <svg viewBox="0 0 320 110" role="img" aria-label="일별 소비 막대">
    <g fill="#5140a6">
      <rect x="30" y="70" width="8" height="30"/><rect x="42" y="50" width="8" height="50"/><rect x="54" y="80" width="8" height="20"/>
      <rect x="66" y="40" width="8" height="60"/><rect x="78" y="65" width="8" height="35"/><rect x="90" y="90" width="8" height="10"/>
      <rect x="102" y="55" width="8" height="45"/><rect x="114" y="75" width="8" height="25"/><rect x="126" y="30" width="8" height="70"/>
      <rect x="138" y="60" width="8" height="40"/><rect x="150" y="85" width="8" height="15"/><rect x="162" y="45" width="8" height="55"/>
      <rect x="174" y="70" width="8" height="30"/><rect x="186" y="58" width="8" height="42"/><rect x="198" y="78" width="8" height="22"/>
      <rect x="210" y="50" width="8" height="50"/><rect x="222" y="66" width="8" height="34"/>
    </g>
    <g fill="#c9c2e8">
      <rect x="234" y="62" width="8" height="38"/><rect x="246" y="64" width="8" height="36"/><rect x="258" y="63" width="8" height="37"/>
      <rect x="270" y="62" width="8" height="38"/><rect x="282" y="64" width="8" height="36"/><rect x="294" y="63" width="8" height="37"/>
    </g>
    <line x1="30" y1="100" x2="310" y2="100" stroke="#e6e3f0"/>
  </svg>
  <div class="helper">연한 막대는 기준일 다음 날부터의 경로 평균(empirical_path_mean)이라 합계가 기간 말 P50 과 같지 않을 수 있어요.</div>
</div>

<p class="note">외식 봉투가 예산을 넘었어요. 지금 흐름이면 기간 말 총소비가 예산보다 <strong>84,000원</strong> 많아요. 남은 8일은 외식을 줄이고 식비 봉투로 옮기면 예산 안에서 끝낼 수 있어요. <span class="source">AI 설명 · 검증된 근거</span></p>
</body>
</html>
`;
