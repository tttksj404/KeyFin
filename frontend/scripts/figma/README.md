# Figma 로컬 플러그인 — 디자인 가져오기

`design/tokens.json`과 `design.pen`의 `P0 화면`(L36Q0u)·`P0 화면 초안`(n3r9i) 프레임을 Figma에 **편집 가능한 노드·변수·스타일**로 재현하는 Figma Plugin API 스크립트다. 커뮤니티 플러그인 없이, Starter 플랜의 내 파일(편집 권한)에서 동작한다.

> **역할**: Pencil(`design.pen`) → Figma **한 방향 내보내기**. 공유·열람용 출력물이며, 코드 구현·대조·토큰의 원천은 Pencil이다(`AGENTS.md` 디자인 원천 절, 규칙 70). Figma에서 고친 내용은 코드로 돌아오지 않는다 — 고칠 것은 Pencil에서 고치고 다시 빌드한다.

## 파일
- `build-plugin.cjs` — 생성기. `tokens.json`(시맨틱 색 × light/dark, 타이포 13, 반경, 크기)과 `design.pen`의 최상위 프레임 서브트리(`SCREEN_IDS`), lucide 아이콘 SVG, 이미지 fill 파일을 읽어 `code.js`를 만든다. Pencil 컴포넌트 인스턴스도 펼친다. `SCREEN_IDS`에 design.pen 최상위에 없는 id가 있으면 최상위 노드 목록을 보여 주고 멈춘다 — 내보낼 범위를 바꾸려면 이 배열을 고친다. `pnpm figma:build`
- `code.template.js` — 플러그인 본문 템플릿. Foundations 프레임 빌더와 `design.pen` 범용 변환기(`buildPenNode`)가 여기 있다. 화면은 전부 `design.pen`에서 오므로 화면을 고치려면 Pencil에서 고치고 다시 빌드한다
- `code.js` — 생성물(약 3.5MB, 대부분 base64 이미지). 직접 수정하지 않는다
- `smoke.cjs` — Figma 없이 `code.js`를 목(mock) API로 실행하는 스모크 테스트. `pnpm figma:smoke`(빌드 → 다중 모드 → Starter 폴백 순으로 실행)
- `manifest.json` — 플러그인 매니페스트

## 실행
1. Pencil에서 `design.pen`을 저장(Ctrl+S)한 뒤 `pnpm figma:smoke` (빌드 + 목 실행, 예외 0이어야 함). 빌드는 디스크의 파일을 읽으므로 저장 전 변경은 빠진다
2. Figma **데스크톱 앱**에서 편집 가능한 **새 파일**(내 Drafts) 열기
3. 메뉴 `Plugins → Development → Import plugin from manifest…` → `scripts/figma/manifest.json` 선택
4. `Plugins → Development → reactNativeHaness design import` 실행 (노드 약 3,900개를 만들므로 수십 초~몇 분 걸릴 수 있다)
5. 완료 알림 후 `Foundations` 페이지(Color style / Text style 프레임), `Screens` 페이지 확인
6. 노드 하나가 실패해도 가져오기는 계속된다. 실패·경고가 있으면 `Screens` 페이지 상단(y < 0)에 **`Import log`** 텍스트가 생기고 알림에 첫 오류가 표시된다 — 그 텍스트를 복사해 전달하면 원인을 좁힐 수 있다. 스택은 `Plugins → Development → Open console`
7. 재실행 전에는 이전 결과(페이지·변수·스타일)를 지우거나 새 파일에서 실행한다(아래 "재실행")

## 만드는 것
- Variables: 컬렉션 `color`(light 모드, 가능하면 dark 모드 추가 — Starter처럼 컬렉션당 모드 1개면 `color/dark` 컬렉션으로 분리), `radius`, `size`
- Styles: `color/light/*`, `color/dark/*` 페인트 스타일, `text/*` 텍스트 스타일
- `Screens` 페이지 — Pencil 캔버스 좌표를 그대로 옮긴다(원점 = 내보내는 프레임들의 좌상단). 프레임 이름은 Pencil 이름 그대로
  - `P0 화면 초안`(0, 0) — 2026-09-14 디자인 개선 전 스냅샷
  - `P0 화면`(오른쪽) — 구현 기준 아트보드(`PAGE-xx 화면명 · 상태`, 흐름 순 배치). 색은 변수 바인딩, `theme.mode: dark` 프레임은 `color` 컬렉션 dark 모드 고정
- 모든 노드에 `pluginData.penId`로 Pencil 노드 ID를 남긴다

## design.pen → Figma 변환 규칙 (`buildPenNode`)
절대 좌표(`layout: none`)·숫자 크기 프레임과 auto-layout·`fill_container`·변수 참조·lucide `icon` 노드를 같은 변환기가 처리한다.

| Pencil | Figma | 비고 |
|---|---|---|
| `frame` | Frame | `layout` none → 절대 좌표, vertical/horizontal(미지정은 Pencil 기본값 horizontal) → auto-layout(gap·padding·justifyContent·alignItems). `clip` → clipsContent, cornerRadius(배열은 모서리별), stroke, effect |
| 크기 `숫자` / `fill_container` / `fit_content`(미지정) | FIXED / FILL / HUG | `layoutPosition: absolute` → ABSOLUTE |
| `$색변수` | 변수 바인딩 | `color` 컬렉션의 같은 이름 변수. `theme.mode: dark`인 프레임은 dark 값으로 칠하고 다크 모드로 고정 |
| `$font-sans` | `tokens.json` `fontFamily.sans`(Pretendard) | Pencil이 Google 폰트만 렌더해 캔버스 값이 대체 서체여도 Figma에는 토큰 서체로 옮긴다 |
| `icon`(lucide) | Frame + Vector | `lucide-react-native`의 SVG를 가져와 stroke/fill을 색 변수에 바인딩. lucide 외 라이브러리는 빌드 실패 |
| `rectangle` / `ellipse` | Rectangle / Ellipse | `sweepAngle`이 ±360이 아니면 arcData |
| `text` | Text | `textGrowth` auto → WIDTH_AND_HEIGHT, fixed-width → HEIGHT, fixed-width-height → NONE. `lineHeight` 비율 → PERCENT |
| `path` | Vector | SVG로 가져온 뒤 안쪽 벡터만 꺼내 Pencil의 x/y/width/height로 맞춘다(Pencil은 geometry의 tight bbox를 노드 박스에 매핑) |
| `group` | Group | 임시 프레임에 자식을 만든 뒤 `figma.group`으로 묶는다. 회전·flip이 있는 그룹(3개)은 원점 보존을 위해 프레임으로 남긴다 |
| 색 hex | Solid paint | 8자리 hex의 알파 → opacity. **토큰 값과 1:1로 일치하는 hex는 `color` 변수에 바인딩**(흰색처럼 여러 토큰이 공유하는 값은 바인딩하지 않음) |
| `effect` shadow / blur / background_blur | DROP_SHADOW·INNER_SHADOW / LAYER_BLUR / BACKGROUND_BLUR | |
| `rotation` | rotation | 둘 다 좌상단 원점 CCW |
| `flipX` / `flipY` | relativeTransform | 근사(노드 박스 중심 기준 반전) |
| 이미지 fill | Image paint | 빌드가 `url`(design.pen 기준 상대경로) 파일을 base64로 `code.js`에 심고 `figma.createImage`로 만든다. `mode` fill/fit/stretch → FILL/FIT/CROP. 파일이 없으면 빌드 실패, Figma가 이미지를 거부하면 회색 `#CACACA` + 경고 |
| `ref`(컴포넌트 인스턴스) | 원본 프레임 + override | 컴포넌트 원본을 펼쳐 변환한다 |

## 서체
텍스트는 Pencil에 적힌 서체(`$font-sans` → Pretendard, 로그인 화면의 `KeyFin` 로고 글자는 `Orbitron`)를 먼저 시도하고, 없으면 `Pretendard` → `Noto Sans KR` → `Inter` 순으로 대체한다(대체하면 콘솔 경고). `Semi Bold`처럼 스타일 이름이 다른 서체는 자동으로 대체한다. Foundations의 텍스트 스타일은 프로젝트 서체 체인만 쓴다.

## 재실행
플러그인은 기존 변수·스타일을 갱신하지 않고 **새로 만든다**. 다시 실행하기 전에 이전 결과(페이지·변수·스타일)를 지우거나 새 파일에서 실행한다.

## 실행 후
필요하면 생성된 프레임 URL(`Copy link`)을 `design/design-map.json`의 `figmaExport.*`에 `url` 필드로 남겨 둔다(공유용 참고, 필수 아님). 코드·토큰 쪽에는 반영할 것이 없다.
