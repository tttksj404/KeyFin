# 모바일 핀테크 앱 — React Native 클라이언트 + 에이전트 하네스

Expo(SDK 57) / React Native 0.86 기반 핀테크 모바일 클라이언트와, AI 코딩 에이전트가 **Pencil(`design.pen`) 디자인 원천**과 **핀테크 보안 규칙**을 일관되게 따르도록 만든 하네스입니다. 백엔드는 Java(Spring) 별도 저장소이며 OpenAPI 스펙으로 계약합니다.

## 기술 스택

| 영역 | 기술 | 상태 |
|---|---|---|
| Runtime | Expo SDK 57 · React Native 0.86 · React 19.2 · TypeScript strict | 설치됨 |
| Routing / Styling | Expo Router · NativeWind v4 | 설치됨 |
| Animation | Reanimated 4 | 설치됨 |
| Room Scene | `@shopify/react-native-skia`(방 씬·스프라이트) · `react-native-gesture-handler`(가구 편집) · `features/room/` | 설치됨 (0단계 스파이크) |
| UI Components | React Native Reusables (shadcn 규약, `components/ui/`) | 설치됨 |
| Server / Client State | TanStack Query · Zustand · axios | 설치됨 |
| Security | expo-secure-store · expo-local-authentication | 설치됨 |
| Icon / Font | lucide-react-native · Pretendard(expo-font, `assets/fonts/`) | 설치됨 (폰트는 개발 빌드에서 적용) |
| Lint / Test | ESLint(`pnpm lint`) · jest-expo + React Native Testing Library(`pnpm test`) | 설치됨 |
| Build | 개발 빌드(expo-dev-client / EAS) 기준. Expo Go는 UI 확인용(Pretendard 미적용) | 결정됨 |
| Package Manager | pnpm 11 (npm/yarn 금지) | 전용 |

## 빠른 시작

```bash
pnpm install
pnpm start            # a / i / w 로 플랫폼 전환

pnpm typecheck        # tsc --noEmit
pnpm lint             # expo lint (ESLint flat config)
pnpm test             # jest-expo + RNTL
pnpm ui:add https://reactnativereusables.com/r/nativewind/<name>.json   # RNR 컴포넌트 추가
pnpm tokens:sync      # design.pen 변수 → design/tokens.json → tailwind.config.js, global.css, lib/theme.ts
pnpm tokens:check     # design.pen↔tokens.json 일치 + 산출물 최신 여부 + UI 코드의 토큰 위반 검사
pnpm harness:sync     # .agents → .claude 미러 동기화
pnpm harness:check    # 미러·JSON·skills-lock·Pencil↔토큰·산출물·design.pen 이미지 참조(고아 파일) 무결성 검사
pnpm figma:build      # (선택) design.pen 화면 + 토큰 → Figma 로컬 플러그인 code.js (공유용 출력물)
```

## 디렉토리 구조

```text
├── design.pen                # Pencil 작업 파일 = 디자인의 확정 원천 (문서 변수 51개 + 아트보드)
├── AGENTS.md                 # 에이전트 진입점 (스택·디렉토리·디자인 원천·승인·보고)
├── CLAUDE.md                 # @AGENTS.md
├── design/                   # 코드가 읽는 디자인 파일
│   ├── tokens.json           #   값 — design.pen 변수에서 sync-pen-tokens.cjs로 동기화 (손으로 수정 금지)
│   ├── DESIGN.md             #   의도 — 톤·타이포·간격·컴포넌트 인벤토리
│   ├── design-map.json       #   화면·컴포넌트 ↔ Pencil 노드 id (+ Figma 내보내기 프레임 이름)
│   └── pencil/               #   대안 드래프트 .pen (메인 파일은 루트 design.pen)
├── .agents/                  # 하네스 정본
│   ├── rules/                #   00~60 기본, 70 디자인 토큰, 80 핀테크 보안, 90 백엔드 계약
│   └── skills/               #   pencil-design · fintech-ui-patterns (프로젝트 전용 2종만)
├── .claude/                  # Claude Code 미러 (rules, skills, settings.json)
├── scripts/                  # sync-pen-tokens · sync-tokens · check-tokens · sync-harness · check-harness · hooks/post-edit-check · figma/(Figma 내보내기 플러그인) · assets/(방 씬 에셋: 배경 제거 remove-white-bg.ps1 · 시트 빌드 build-sprite-sheet.ps1, Windows PowerShell)
├── assets/sprites/           # 방 씬 앱 에셋(Git LFS 대상): floors/ furniture/ characters/(시트 .png + 프레임 .json)
├── docs/                     # frontend-spec.md(KeyFin 기능·화면 명세) · api-guide.md(통신 코드 절차) · api-contract.md(Notion API 명세 사본) · 코드 품질 기준(토스 Frontend Fundamentals, Clean Code)
├── app/                      # Expo Router 라우트 — 화면 조립만
├── features/<domain>/        # auth · settings · link · account · transaction · budget · payment · room · shop · notification · coaching · home (api/, components/, model.ts)
├── components/ui/            # RNR 벤더 컴포넌트 + 프로젝트 컴포넌트 (이름 = Pencil 컴포넌트명)
├── components.json           # RNR/shadcn CLI 설정 (별칭 @/)
├── lib/                      # utils.ts(cn) · query-client.ts · money.ts · mask.ts · date.ts · theme.ts(생성)
├── assets/fonts/             # Pretendard 정적 서체 4종 (OFL)
├── api/                      # client.ts · generated/(OpenAPI) · mocks/
├── tailwind.config.js        # 생성 파일
├── global.css                # 생성 파일 (CSS 변수로 라이트/다크 전환)
└── skills-lock.json          # 스킬 출처·체크섬
```

## 방 가구 일괄 저장

- 방 꾸미기는 방 조회 후 전체 보유 목록을 새로 받아 편집을 시작한다. 편집 중 이동·보관·배치는 사본에만 반영한다.
- 완료할 때 `PUT /api/v1/furnitures/placements`에 `{ placements: [...] }`를 한 번 보낸다. 변경하지 않은 가구까지 **최종 설치 가구 전체**를 포함하며, 빠진 보유 가구는 보관된다.
- 항목에는 `userFurnitureId`, `placementStatus`, `placementDirection`, `positionX`, `positionY`, `layer`만 보낸다. 최대 100개, X 0~327, Y 0~586, 좌표 소수 3자리, 정수 layer를 사용한다.
- `furnitureType`은 서버 분류다. 최종 배치에는 소파·TV·식탁·커피테이블이 각각 정확히 하나 있어야 한다. 기본 가구를 ‘넣어 두기’로 보관한 뒤 구매 가구를 꺼내 교체할 수 있다. `canUnplace=false`는 단건 해제 제한이며 일괄 편집의 보관 제한이 아니다.
- 서버 ID가 없는 보드·캘린더 등 앱 전용 오브젝트는 요청에서 제외한다. 화면에 표현하지 못하는 설치 가구는 서버 원본 면·방향·좌표·layer를 함께 보내 보존한다. 필수 원본 정보가 잘못되었으면 저장을 차단한다.
- 저장 중에는 편집·뒤로 이동을 잠근다. 실패하면 사본을 유지하고 다시 저장할 수 있다. 성공 응답의 전체 보유 목록으로 상태를 갱신하고 방을 재조회한다. 조회 실패는 이미 성공한 PUT을 실패로 취급하지 않는다.
- 딱지 승계와 초과 상태가 계속되는 동안의 재부착 방지는 서버에서 처리한다. 예산 복구 시 모든 딱지를 제거하고, 다시 초과하면 같은 예산 기간이라도 그때 설치된 모든 바닥 가구에 다시 붙인다. 설치된 바닥 가구의 딱지는 하루 횟수 제한 없이 한 개씩 제거할 수 있다. `removableToday`는 호환성을 위해 이름을 유지하며, 설치된 바닥 가구에 딱지가 남아 있으면 `true`다. 별도 DB 수정이나 단건 PATCH로의 대체 호출은 하지 않는다. 일괄 저장 API와 `furnitureType`·`stickerAttached` 응답 필드가 배포된 서버가 필요하다.

## 디자인 흐름

```
design.pen (Pencil — 확정 원천: 변수 51개 + 아트보드)
   ├─ sync-pen-tokens.cjs ──▶ design/tokens.json ──sync-tokens.cjs──▶ tailwind.config.js · global.css · lib/theme.ts
   │                                                                         │  규칙 70: 시맨틱 토큰만 사용
   ├─ 구현 전 대조 (Pencil MCP Get · TakeScreenshot, design-map.json 노드 id) ─▶ components/ui(RNR) · features 구현 → tokens:check
   └─ (선택) pnpm figma:build ──▶ Figma   ← 공유·열람용 출력물. 코드는 Figma를 읽지 않는다
```

- 시맨틱 토큰(shadcn 규약)만 className에 노출됩니다(`bg-background`, `bg-card`, `text-foreground`, `text-muted-foreground`, `bg-primary`, `text-destructive`, `text-positive`, `text-h1`, `text-amount-lg`). 프리미티브 팔레트·hex·arbitrary value는 `tokens:check`가 잡습니다(RNR 벤더 파일은 arbitrary/팔레트 검사 면제).
- 라이트/다크는 CSS 변수(`:root` / `.dark:root`, `darkMode: "class"`)로 전환되어 색상에 `dark:` 변형이 필요 없습니다. 기본은 시스템 설정, 수동 전환은 NativeWind `setColorScheme`.
- 토큰 변경은 Pencil 변수(`SetVariables`) → `pnpm tokens:sync` 순서만 허용됩니다. `tokens:check`(훅·CI)가 `design.pen`과 `tokens.json`의 불일치를 잡습니다.
- 화면을 만들기 전 `design/design-map.json`의 Pencil 노드를 MCP `Get`(프레임 fill·layout 포함)·`TakeScreenshot`으로 대조합니다(`pencil-design` 스킬 절차 B). 노드가 `없음`이면 `DESIGN.md` 기준으로 만들고 "Pencil 미대조"로 보고합니다.

## 규칙 요약

| 파일 | 적용 경로 | 핵심 |
|---|---|---|
| `00-baseline` | app, components, features, hooks, lib, 설정 | 범위 준수, NativeWind 전용, 서버 데이터는 Query |
| `10-react-state` | app, components, features, hooks | 상태 5분류, Query/Zustand, Hook 선택 |
| `20-api-data` | api, features/**/api, queries, mutations | 5계층 호출, Key 팩토리, AbortSignal |
| `30-typescript-structure` | app, components, features, hooks, lib | strict, 단일 책임, 파일 배치 |
| `40-styling-accessibility` | app, components, features, css | 토큰, Pressable/FlatList, SafeArea, 접근성 |
| `50-error-security` | app, components, features, hooks, lib, env | 오류 UX, 로깅, SecureStore |
| `60-dependencies-tests` | package.json, 설정, 테스트 | pnpm 전용, 사전 승인, jest-expo |
| `70-design-tokens` | app, components, features, design, 생성 파일 | 토큰 원천(Pencil)·산출물, RNR 벤더 규약, Pencil 대조 |
| `80-fintech-security` | app, components, features, hooks, lib, api | 금액 정밀도, 멱등성, PIN/생체, 마스킹, 로깅 |
| `90-backend-contract` | api, queries, mutations, openapi | OpenAPI 원천, DTO↔모델, 오류 봉투, 헤더 |

## 스킬

| 스킬 | 출처 | 용도 |
|---|---|---|
| `pencil-design` | 프로젝트 | Pencil = 확정 원천. A 화면 드래프트 · B 구현 전 대조 · C 변수 → tokens.json 동기화 |
| `fintech-ui-patterns` | 프로젝트 | 금액·계좌·거래·이체·PIN·오류 패턴 체크리스트 |

외부 스킬 5종(`frontend-design`, `ui-ux-pro-max`, `vercel-react-best-practices`, `design-system`, `brand`)은 웹 전제 지침이라 2026-09-08 제거했습니다. 필요한 원칙은 `.agents/rules/`에 있습니다.

## Pencil / Figma 사용 전제

- Pencil MCP는 에디터에 `.pen` 파일이 열려 있어야 응답합니다. 허용 도구: `get_app_state`, `get_style`, `read_skill`(읽기), `execute`(쓰기, 확인 후). `design.pen`은 평문 JSON이지만 3.8MB라 에이전트는 MCP로 읽고, 스크립트(`sync-pen-tokens.cjs`, `figma/build-plugin.cjs`)만 파일을 직접 읽습니다.
- Figma는 코드에 관여하지 않습니다. `scripts/figma/`의 로컬 플러그인이 Pencil 화면·토큰을 Figma로 **내보내기만** 하며(공유·열람용), 코드 구현·대조·토큰의 근거로 Figma를 읽지 않습니다. `.claude/settings.json`의 Figma MCP 도구 허용은 남아 있으나 하네스 절차에서는 쓰지 않습니다.

## 자동 검사

- **Claude Code 훅** (`.claude/settings.json` → `scripts/hooks/post-edit-check.sh`): `app/ components/ features/ lib/` 편집 후 토큰 위반 검사 자동 실행(위반 시 Claude에게 오류 반환), `design/tokens.json` 편집 후 산출물 재생성, `.agents/` 편집 후 `.claude/` 미러 동기화.
- **CI 워크플로 없음**(2026-09-01 제거): push 전 검증은 로컬 명령 `typecheck · lint · test · tokens:check · harness:check`로 수행합니다. `tokens:check`와 `harness:check`에 `design.pen ↔ tokens.json` 일치 검사가 들어 있어 Pencil을 바꾸고 동기화하지 않으면 실패합니다.

## 하네스 유지보수

- 규칙은 `.agents/rules/NN-topic.md`에 `paths` frontmatter와 함께 작성하고 `pnpm harness:sync`로 미러를 갱신합니다.
- 외부 스킬을 갱신하면 `skills-lock.json`의 해시를 다시 계산합니다.
- 토큰 변경은 Pencil 변수 → `pnpm tokens:sync` 순서로만 합니다. Pencil 변수에 없는 토큰(타이포·모션·그림자·`radius.full`)만 승인 후 `tokens.json`에서 직접 관리합니다.

## 라이선스

MIT (`LICENSE`). 각 외부 스킬은 해당 저장소의 라이선스를 따릅니다.

## Preview 업데이트 배포

실기기용 APK 최초 설치, EAS Update 배포, 환경변수와 재빌드 기준은 [Preview 배포 안내](./PREVIEW_UPDATES.md)를 참고하세요.
