# 디자인 스펙 (DESIGN.md)

> 이 문서는 UI 작업의 **원천 문서**다. 값의 원천은 `design/tokens.json`이며, 이 문서는 그 값을 어떤 의도로 쓰는지 설명한다.
> 2026-08-30 `design.pen`에 붙여넣은 Figma UI 킷(보라 `#3629B7` primary, Poppins, radius 15, 화면 10개)에서 값을 추출해 `tokens.json`에 반영했다. 2026-08-30 저녁 **Pencil(`design.pen`)을 단일 확정 원천으로 확정** — 토큰은 Pencil 문서 변수에서 `scripts/sync-pen-tokens.cjs`로 동기화하고(`$source.pencilSyncedAt`), Figma는 `pnpm figma:build` 출력물일 뿐 코드가 읽지 않는다. 사용자 결정(2026-08-30): 입금 green/출금 red 유지, Pretendard 유지, positive 킷 값 그대로, 다크 모드는 파생, CTA 56 유지, 모서리는 킷 그대로.
>
> 상태: **킷 반영 · Pencil 단일 원천 (design.pen 변수 ↔ tokens.json 동기화 검사 중)**

## 1. 제품 성격과 디자인 톤

- 도메인: 모바일 핀테크(계좌 조회, 이체, 결제, 인증). 사용자는 돈을 다루므로 **신뢰·정확·차분함**이 최우선이다.
- 톤 키워드: 신뢰(Trust), 명료(Clarity), 절제(Restraint). 화려함보다 정보의 정확한 위계.
- 무드(킷): 라이트 모드는 **흰 캔버스 + 흰 카드(옅은 보라 그림자)**, 옅은 보라(`muted` `#F2F1F9`)로 입력·비활성 영역 구분. 다크 모드는 킷에 없어 보라 톤 navy(`night` 스케일)로 파생 `[확인]`. 순수 검정(`#000`) 배경은 쓰지 않는다.
- 포인트 컬러는 브랜드 퍼플 하나(`primary` `#3629B7`). 오렌지(`highlight` `#FB6B18`)는 강조에 한 화면당 한 곳만. 카테고리 아이콘은 킷처럼 `primary`·`destructive`·`info`·`warning`·`positive`·`highlight`를 섞어 쓴다.
- 계좌 카드는 `bg-primary` 위 흰 텍스트의 단색 사각형(킷 Card Bank의 장식 원은 붙여넣기에서 깨져 사용하지 않음 — 사용자 결정 2026-08-30).
- 그라데이션, 글래스모피즘, 장식용 일러스트는 온보딩·이벤트 배너 외에는 쓰지 않는다.
- 아이콘은 `lucide-react-native` 단일 세트, `components/ui/icon.tsx`의 `Icon`으로 감싸 className을 적용한다. 이모지 아이콘 금지.

## 2. 색상 토큰 (shadcn / React Native Reusables 규약)

시맨틱 토큰만 사용한다. 프리미티브(`blue-800`, `slate-200`)는 `tailwind.config.js`에 노출되지 않으므로 className에서 쓸 수 없다. 예외: `white`, `black`(모드 무관 고정값).

규약: `X` = 배경, `X-foreground` = 그 위의 텍스트, `X-muted` = 옅은 배경(배지·강조 영역).

| 역할 | 토큰 | className 예 |
|---|---|---|
| 화면 배경 | `background` / `foreground` | `bg-background text-foreground` |
| 카드·목록 항목 | `card` / `card-foreground` | `bg-card` (RNR `Card`) |
| 다이얼로그·시트·메뉴 | `popover` / `popover-foreground` | `bg-popover` |
| 주요 버튼·활성·링크 | `primary` / `primary-foreground` | `bg-primary text-primary-foreground` (RNR `Button` default) |
| 보조 버튼 | `secondary` / `secondary-foreground` | RNR `Button variant="secondary"` |
| 입력 배경·스켈레톤·비활성 | `muted` / `muted-foreground` | `bg-muted`, 보조 텍스트 `text-muted-foreground` |
| 눌림·선택 배경 | `accent` / `accent-foreground` | RNR ghost/outline active |
| 출금·손실·오류·파괴적 액션 | `destructive` / `destructive-foreground` / `destructive-muted` | `text-destructive`, 배지 `bg-destructive-muted text-destructive` |
| 입금·수익·성공 | `positive` / `positive-foreground` / `positive-muted` | `text-positive`, 배지 `bg-positive-muted text-positive` |
| 경고 | `warning` / `warning-foreground` / `warning-muted` | `text-warning` |
| 정보 | `info` / `info-foreground` / `info-muted` | `bg-info-muted text-info` |
| 강조 오렌지 | `highlight` / `highlight-foreground` | `text-highlight` |
| 토스트·툴팁 | `inverse` / `inverse-foreground` | `bg-inverse text-inverse-foreground` |
| 테두리 | `border` | `border-border` |
| 입력 테두리 | `input` | `border-input` (RNR `Input`) |
| 포커스 링 | `ring` | `border-ring` |
| 오버레이 | `black/50` | 다이얼로그 스크림 (RNR `Dialog`) |

### 금액 부호 색상 (명시 규칙)

- 이 프로젝트에서 **입금/수익 = `positive`(green), 출금/손실 = `destructive`(red)** 로 고정한다. 킷은 입금·출금 모두 빨강을 쓰지만 따르지 않는다(사용자 결정 2026-08-30).
- `positive` `#52D5BA`는 흰 배경 텍스트 대비가 약 2:1로 낮다. 킷 값 그대로 쓰기로 했으므로(2026-08-30) 금액 부호·텍스트를 항상 함께 두어 색에만 의존하지 않는다.
- 증권 시세(상승 빨강·하락 파랑)의 한국 관례를 따라야 하는 화면이 생기면 별도 토큰(`up`/`down`)을 Pencil 변수에 추가한 뒤 동기화한다. 기존 토큰의 의미를 바꾸지 않는다.
- 색만으로 의미를 전달하지 않는다. 금액 앞에 `+`/`-` 부호 또는 "입금"/"출금" 텍스트를 항상 함께 둔다.

### 라이트/다크

- `global.css`의 `:root`(라이트)와 `.dark:root`(다크) CSS 변수로 전환된다. `darkMode: "class"`이며 NativeWind `useColorScheme()`의 `setColorScheme('light' | 'dark' | 'system')`으로 제어한다. 기본은 시스템 설정을 따른다.
- 색상에 `dark:` variant를 직접 쓰지 않는다. 다크에서 구조가 달라지는 경우(그림자 → 테두리)에만 `dark:`를 쓴다. RNR 컴포넌트 원본에 포함된 `dark:` 클래스는 그대로 둔다.

## 3. 타이포그래피

- 서체: **Pretendard** 단일 패밀리. `app.json`의 `expo-font` 플러그인으로 등록되어 있으며(`assets/fonts/Pretendard-{Regular,Medium,SemiBold,Bold}.otf`) Android는 `fontDefinitions`로 weight가 매핑되어 `fontWeight`만으로 굵기 파일이 선택된다. **개발 빌드(`expo prebuild`/EAS)에서 적용되며 Expo Go에서는 시스템 폰트로 폴백**된다.
- `components/ui/text.tsx`의 `Text`가 기본 클래스에 `font-sans`를 포함하므로 모든 텍스트는 이 `Text`를 사용한다. React Native `Text`를 직접 쓰지 않는다.
- 서체 크기·굵기·행간은 킷 Text style(Poppins)의 값을 Pretendard에 그대로 적용한다(Poppins는 한글 미지원).
- 가중치: 400(본문), 500(라벨·캡션·버튼), 600(제목·금액), 700(디스플레이·큰 금액). 세 단계 이상을 한 컴포넌트에 섞지 않는다.
- 금액과 숫자 열은 항상 `tabular-nums` 클래스를 함께 쓴다.
- 한글 제목은 `letterSpacing` 음수(-0.3 ~ -0.5). 본문은 0.
- 최소 크기 12pt. 본문 기본 16pt.
- 시스템 글꼴 크기 조정을 존중한다. 금액 표시는 `maxFontSizeMultiplier={1.3}`로 레이아웃 붕괴를 막되 비활성화하지 않는다.

타이포 토큰 클래스는 크기·행간·자간·가중치를 함께 설정한다. Tailwind 기본 `text-sm`, `text-base` 등은 RNR 컴포넌트 내부용으로 유지되며, 화면 코드에서는 아래 토큰을 우선한다.

| 클래스 | 크기/행간 | 가중치 | 용도 |
|---|---|---|---|
| `text-display` | 32/40 | 700 | 온보딩 헤드라인 |
| `text-amount-lg` | 36/44 tabular | 700 | 잔액, 이체 금액 입력 |
| `text-amount-md` | 24/32 tabular | 600 | 카드 내 잔액 |
| `text-amount-sm` | 16/24 tabular | 600 | 거래 목록 금액 |
| `text-h1` | 24/28 | 600 | 화면 제목 (킷 Title 1) |
| `text-h2` | 20/28 | 600 | 섹션 제목 (킷 Title 2) |
| `text-h3` | 16/24 | 600 | 카드 제목 (킷 Title 3) |
| `text-body-lg` | 18/28 | 400 | 강조 본문 |
| `text-body` | 16/24 | 400 | 기본 본문 (킷 Body 2) |
| `text-body-sm` | 15/22 | 400 | 보조 설명 (2026-09-14 14→15, 폰에서 작게 느껴져 올림) |

화면 헤더 제목은 탭 헤더(예산관리·자산관리)와 뒤로가기 헤더(`<` + 제목) 모두 `text-h1`(24) 한 가지다(2026-09-14 통일). `text-h3` 는 본문 섹션 제목에만 쓴다.

봉투 7종은 정체성 색을 갖는다(2026-09-14, 토큰 `env-dining`·`env-transport`·`env-health`·`env-leisure`·`env-shopping`·`env-grocery`·`env-etc` + `-muted`): 아이콘 타일은 `bg-env-*-muted` + `text-env-*`, 소비 분석 막대는 `bg-env-*`. 클래스 묶음은 `features/budget/catalog.ts`의 `envelopeTone(id)`에서만 가져온다. 사용률 막대(예산 탭·봉투 상세·홈)는 상태색 `positive`/`warning`/`destructive`를 그대로 쓴다 — 정체성 색과 상태색을 섞지 않는다.

카드(`bg-card` 면, `rounded-2xl p-5`)는 두 경우에만 쓴다(2026-09-14 규칙): ① 눌러서 어딘가로 가는 목록 항목(결제 캘린더 항목·고정지출 관리 항목·자산 탭 계좌/카드·빠른 메뉴·수입 계좌 선택지) ② 선택지·버튼이 한 덩어리로 묶인 것(미확정 정리 항목·코치 말풍선·팝오버). 정보를 보여주기만 하는 덩어리(총예산·준비할 금액·설정 동의·거래/봉투 요약)는 카드 없이 본문에 바로 놓고, 상태 안내는 `*-muted` 색 띠(`rounded-lg p-3.5`)로 한다.

라이트 모드 배경은 브랜드 기 없는 중립 `background` #FCFCFC(2026-09-16 사용자 결정 — #F6F5FB → #FAF9FD 를 거쳐 보라 기를 빼고 흰색에 가깝게)이고 `card` 는 흰색이다. 배경과 카드 차이가 거의 없어 면 구분은 그림자가 맡는다: 헤더 `shadow-md shadow-black/10`, 탭바는 같은 세기의 위쪽 그림자(`tab-bar.tsx` 스타일 상수), 목록 항목은 `bg-card rounded-lg p-4` + `shadow shadow-black/10`(다크는 `dark:border dark:border-border dark:shadow-none`)로 면을 나누고, 그 안의 아이콘 타일은 `bg-accent` 원(#EAE8F5)으로 한다(자산 탭 계좌·카드, 결제 캘린더, 고정지출 관리, 약관 전체 동의 적용). `accent`·`muted`·`secondary` 는 tint 배경에 묻히지 않도록 한 단계 진한 #EAE8F5 다 — 칩·탭 활성·눌림 상태·트랙·아이콘 원에만 쓰고 목록 항목 면으로는 쓰지 않는다. 2026-09-15 까지는 background 와 card 가 둘 다 흰색이라 항목을 `bg-accent` 면으로 두었는데, tint 도입으로 뒤집었다. 같은 목록 안에서 일부 항목만 눌리지 않게 두지 않는다 — 고칠 수 없는 항목도 읽기 전용 상세로 연다.

섹션 구분(2026-09-15 사용자 규칙, 앞으로 모든 화면): 자산 탭처럼 섹션 제목은 `text-h2 text-foreground`(한 섹션 안의 하위 묶음·날짜 묶음은 `text-h3 text-foreground`)로 크고 검게 쓰고, 섹션 사이는 40(`gap-10`, 2026-09-16 사용자 요청으로 32 에서 올림 — 스크롤 컨테이너의 `contentContainerClassName` 에 두어 화면마다 같은 값이 되게 한다)·제목과 내용 사이는 12(`gap-3`)로 띄운다. 작은 보조색 라벨(`text-label`·`text-caption` + `text-muted-foreground`/`text-card-foreground`)을 섹션 제목으로 쓰지 않는다. Pencil 에서도 섹션 제목은 `$foreground` 20/600(하위 16/600)이다.
| `text-label` | 15/22 | 500 | 입력 라벨, 탭, 카테고리명 (킷 Body 3, 2026-09-14 14→15) |
| `text-caption` | 13/18 | 500 | 날짜, 상태, 법적 고지 (킷 Caption 2, 2026-09-14 12→13) |
| `text-button` | 16/24 | 500 | 버튼 (킷 Button 라벨) |

## 4. 간격 · 형태 · 크기

- 4px 그리드(Tailwind 기본 스케일). 화면 좌우 패딩 `px-5`(20). 카드 내부 `p-4`(16). 섹션 간격 `gap-10`(40, 2장 섹션 규칙).
- **헤더 없는 화면의 상단 여백은 상태바 높이 + 20** 이다(2026-09-18 사용자 결정). 탭 화면은 탭바가 현재 위치를 알려 주므로 제목 헤더를 두지 않고 이 여백만 준다 — `components/ui/screen.tsx` 의 `useHeaderlessTop()`(= `useTopInset()` + `HEADERLESS_TOP_GAP` 20)을 쓰고 숫자를 화면에 직접 적지 않는다. 뒤로가기가 있는 상세·온보딩 화면은 `ScreenHeader` 를 그대로 쓴다.
- 모서리(킷): 배지 `rounded-sm`(6), 거래 행 아이콘 타일 `rounded-md`(10), **버튼·입력·카드·금액 칩·탭 `rounded-lg`(15)**, 바텀시트 `rounded-xl`(20). RNR `Button`·`Input`·`Card` 기본 클래스는 벤더 원본을 유지하므로 화면에서 `className="rounded-lg"`로 덮어쓴다.
- 그림자(킷 `shadow.card`: 0/4, blur 30, `primary` 7%): 산출물에 아직 없어 `shadow-sm shadow-black/5`로 근사한다. 다크 모드에서는 그림자 대신 `border-border`.
- 터치 타깃 최소 44pt(`min-h-touch min-w-touch`). 주요 CTA 높이 `h-button-lg`(56, 사용자 결정), 일반 버튼 `h-button-md`(44, 킷), 입력 `h-input`(44, 킷). 아이콘 `w-icon`(24) `w-icon-sm`(20) `w-icon-lg`(28, 카테고리), 아이콘 타일 `w-icon-tile`(40), 아바타 `w-avatar`(50).
- 모션: `duration-fast/base/slow` = 150/220/320ms. 화면 전환은 플랫폼 기본. 금액 카운트업 같은 장식 애니메이션은 쓰지 않는다.

## 5. 컴포넌트 인벤토리

### 5-1. React Native Reusables (설치됨, `components/ui/`)

`pnpm ui:add https://reactnativereusables.com/r/nativewind/<name>.json`으로 추가한다. 추가 후 `pnpm tokens:check`를 통과하도록 arbitrary value만 조정하고 나머지는 원본을 유지한다.

| 파일 | 내보내기 | 비고 |
|---|---|---|
| `text.tsx` | `Text`, `TextClassContext` | 기본 클래스에 `font-sans` 추가(프로젝트 수정) |
| `button.tsx` | `Button`, `buttonVariants` | variant `default(primary)` `secondary` `outline` `ghost` `destructive` `link`, size `default` `sm` `lg` `icon` |
| `input.tsx` | `Input` | `border-input bg-background` |
| `card.tsx` | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter` | `bg-card rounded-xl` |
| `badge.tsx` | `Badge` | variant `default` `secondary` `destructive` `outline` |
| `skeleton.tsx` | `Skeleton` | `bg-muted` |
| `separator.tsx` | `Separator` | |
| `icon.tsx` | `Icon` | lucide 아이콘 래퍼, `className`으로 색·크기 |
| `dialog.tsx` | `Dialog`, `DialogTrigger`, `DialogContent`, … | 루트 레이아웃의 `PortalHost` 필요(설정됨) |

### 5-2. 프로젝트 전용 (Pencil 컴포넌트명 = 코드명)

| Pencil 컴포넌트 | 코드 | 기반 | variant / size |
|---|---|---|---|
| `AmountText` | `components/ui/amount-text.tsx` | `Text` | `lg` `md` `sm`, `sign` |
| `AmountInput` | `components/ui/amount-input.tsx` | `Input` | 통화 `KRW` 고정, 콤마 포맷. `variant="hero"`(기본, 36pt + 빠른 금액 칩 — 이체 금액) / `"field"`(폼의 한 칸, 다른 입력칸과 같은 16pt + '원', 칩 없음 — 고정지출 등록, 2026-09-14) |
| `EmptyState` | `components/ui/empty-state.tsx` | `Text`, `Icon`, `Button` | 빈 목록·오류 |
| `LottieLoop` | `components/ui/lottie-loop.tsx` | `lottie-react-native` (+ 웹 `@lottiefiles/dotlottie-react`) | 반복 재생 · 동작 줄이기면 정지 · 기기와 웹 모두 재생. 기다림·성공 순간(분석 중·입주 연출·이체 완료)에만 쓰고 입력 화면에는 쓰지 않는다. 에셋 `assets/lottie/*.json` 100KB 이하 |
| `FillBar` | `components/ui/fill-bar.tsx` | Reanimated | 가로 진행 막대 한 종류(트랙 `bg-muted rounded-full`, 기본 `h-2`). `fillDelay` 를 주면 진입 시 0 에서 차오름(900ms). 소비 분석 막대·예산 탭 사용률 막대 |
| `Floating` | `components/ui/floating.tsx` | Reanimated | 캐릭터 정지 이미지 둥실거림(`distance` 6 · `period` 2400ms) · 동작 줄이기면 정지. 로그인 캐릭터·`CoachRow` |
| `CountUpAmount` | `components/ui/count-up-amount.tsx` | `Text`, `hooks/use-count-up` | 화면의 주인공 금액이 0 → 값으로 0.9초 굴러 올라감(값이 바뀌면 이어서). 소비 분석 합계·예산 잔액·예산 설정 총액·홈 예산 카드. 목록 행 금액에는 쓰지 않는다. 동작 줄이기면 정지 |
| `ScreenHeader` | `components/ui/screen-header.tsx` | `Icon`, `Text`, `Pressable`, Reanimated | Pencil `ScreenHeader`(tdgU8) — `<`(24) + `text-h1` 제목 + 오른쪽 액션 슬롯(`children` 로 행 교체 가능 — 홈 인사말). tint 배경 위 흰 면: `bg-card border-b border-border px-6 pb-3 shadow-sm shadow-black/5 dark:shadow-none`, 상태바 영역은 헤더가 `SafeAreaInsetsContext.top` 만큼 직접 칠한다(라우트에 SafeAreaView 없음). `Screen` 안에서는 본문 위에 떠 있다가 48px 스크롤하면 투명해지고 제목·뒤로가기도 사라지며(터치는 본문으로), 맨 위로 오면 돌아온다. 헤더 자리는 같은 높이 빈 공간 + 24 로 흐름에 남는다. `Screen` 밖(스크롤 없는 화면)에서는 흐름 안 고정 바 + `mb-6`. 모든 화면 헤더가 이것 하나다. 2026-09-16 |
| `BottomSheet` | `components/ui/bottom-sheet.tsx` | `Modal`, `Pressable`, Reanimated | Pencil 없음(동작 컴포넌트). 아래서 올라오는 시트: 열릴 때 스크림 220ms 페이드 + 시트 280ms 슬라이드, 닫힐 때 반대로(시트가 다 내려간 뒤 모달을 내림). 홈 예산 시트·세분류 시트·거래 필터 선택창이 쓴다. 2026-09-16 |
| `Screen` / `ScreenScrollView` / `ScreenFlatList` | `components/ui/screen.tsx` | `ScrollView`, `FlatList`, Reanimated shared value | Pencil 없음(동작 컴포넌트). 헤더가 겹치는 화면의 뿌리(`flex-1 bg-background` + 스크롤 값·헤더 높이 컨텍스트)와, 그 안에서 헤더 자리만큼 위로 당겨져(`marginTop: -(헤더+24)`) 내용이 헤더 아래로 지나가는 스크롤 컨테이너. `Screen` 밖에서는 보통 ScrollView/FlatList 와 같다. 스크롤 있는 헤더 화면 18개가 쓴다. 2026-09-16 |
| `CoachRow` | `components/ui/coach-row.tsx` | `Floating`, `Text` | 온보딩 코치 행 — 캐릭터 76×112 + 말풍선 `bg-card border-border rounded-lg p-3.5 text-label`(홈 코치 말풍선과 같은 스타일). 회원가입·약관·금융망 이메일 |
| `Toast` | `components/ui/toast.tsx` | — | `info` `success` `error`, `bg-inverse` |
| `BottomSheet` | `components/ui/bottom-sheet.tsx` | `Dialog` 또는 별도 | `bg-popover` |
| `ListGroup` | `components/ui/list-group.tsx` | `Separator` | 설정·메뉴 목록 |
| `TabBar` | `components/ui/tab-bar.tsx` | `Pressable`, `Icon`, `Text` | Pencil 홈 `BottomTabBar`(NaYk9) — 탭 4개(홈·자산·예산·마이, 리포트는 2026-09-23 제외), 아이콘 20 + `text-caption` 라벨 상시 표시. 활성 탭은 `bg-accent rounded-lg` + `text-primary`, 비활성은 `text-muted-foreground`. 바탕 `bg-card`, 상단 `border-border`. `app/(tabs)/_layout.tsx`의 `tabBar` |
| `CharacterRoom` | `features/home/components/CharacterRoom.tsx` | `Image`, `Pressable` | Pencil 홈 `CharacterRoom`(Rj36w · Plvf1) — 좌우 여백 24, 이미지 `rounded-xl`. 캐릭터 없음: 빈 방 이미지 전체가 "캐릭터를 등록하세요" 버튼(327×596). 캐릭터 있음: 캐릭터 방 이미지(327×404) |
| `BudgetCard` | `features/home/components/BudgetCard.tsx` | `Text` | Pencil `BudgetCard`(oIAhy) — `bg-primary rounded-xl p-5 gap-4`, 제목 `text-h3`, 상태 라벨 `text-caption text-positive`, 남은 예산 `text-display tabular-nums`, 설명 `text-caption`, 진행 바 `h-2 rounded-full bg-accent` + `bg-positive` |
| `SignupScreen` | `features/auth/components/SignupScreen.tsx` | `Text`, `Input`, `Button`, `Icon` | Pencil `signup`(ZjEHu) · `signup/error`(UdUD7) · `signup/pending`(b1O9sc) — 뒤로가기 헤더 + `text-h1` 제목, 이름·이메일·비밀번호 3필드(`h-input rounded-lg`). 중복 이메일은 이메일 필드 아래 `text-destructive` 아이콘+문구, 하단 CTA `h-button-lg` |
| `LoginScreen` | `features/auth/components/LoginScreen.tsx` | `Text`, `Input`, `Button`, `Icon` | Pencil `login`(HUL5i) · `login/error`(JF0Db) · `login/pending`(bG1FL) — 좌우 여백 24, 상단 `pt-16`. 상단은 킷 로고 PNG(`assets/brand/keyfin-logo.png`, `h-24 w-full` + `resizeMode="contain"`). 입력은 `h-input rounded-lg`, 오류 시 `border-destructive` + 아이콘·문구. 하단 CTA `h-button-lg`, 그 아래 회원가입 링크 |
| `Slider` | `components/ui/slider.tsx` | `View` | Pencil `budget-proposal` `Slider`(i3IyGs) — 트랙 `h-1.5 bg-muted`, 채움 `bg-primary`, 손잡이 18 `bg-primary` + 6 `bg-primary-foreground` 점. RN 코어 responder 이벤트만 써서 웹에서도 같게 동작. `accessibilityRole="adjustable"` |
| `BudgetProposalScreen` | `features/budget/components/BudgetProposalScreen.tsx` | `Text`, `Icon`, `Slider`, `Button`, `Skeleton`, `EmptyState` | Pencil `budget-proposal`(g1fhiV) · `budget-proposal/full`(VAJgp) — 헤더 `bg-card` 뒤로가기 + `text-h3` 제목, 본문 `px-6 gap-5`. 총 예산 카드 `bg-card rounded-2xl p-5` + `text-amount-md`(합계 실시간). 봉투 행은 28 `bg-accent rounded-md` 타일 + `text-label` 이름 + `bg-muted rounded-md` 금액칸 + 슬라이더 + `text-caption` 월평균 근거. CTA 는 하단 고정 `h-button-lg` |
| `EnvelopeCarousel` | `features/budget/components/EnvelopeCarousel.tsx` | `Pressable`, `FillBar`, `Icon`, `Text`, Reanimated, Gesture Handler | **Pencil 없음(미대조)** — 예산 탭의 봉투 목록을 대신하는 원판 캐러셀(2026-09-18 사용자 결정). 세로로 긴 카드(폭 화면 46%·최대 184, 높이 244, `rounded-3xl bg-card`)를 원에 얹어 x=sin·y=cos(뒤로 갈수록 위로 52)로 놓고, 크기(0.68~1)·투명도(0.3~1)·겹침 순서는 앞뒤(cos)에서 나온다. 좌우 드래그로 돌리고 놓으면 가장 가까운 카드로 스프링 스냅(원판이라 끝에서 처음으로 이어짐). **정면 카드를 누르면 봉투 상세**, 옆 카드를 누르면 그 카드가 정면으로 돌아온다. 아래 점 표시는 장식(보조 기술에서 제외) |
| `BudgetScreen` | `features/budget/components/BudgetScreen.tsx` | `Text`, `Icon`, `Skeleton`, `EmptyState` | Pencil `budget`(kvc1e) · `budget/proposed`(ZOmXC) — 헤더 `bg-card border-b border-border px-6 pb-3` + `text-h1` 제목·`menu` 아이콘, 본문 `px-6 gap-5`. 총예산 카드 `bg-card rounded-2xl p-5 gap-3` + `text-amount-lg` + 진행 바 `h-2`. 봉투 행은 28 `bg-accent rounded-md` 아이콘 타일 + `text-label` 이름 + `text-amount-sm` 금액 + `h-1.5` 사용률 바(`bg-positive`/`bg-warning`/`bg-destructive`). 확정 전(PROPOSED) 주기는 이 탭 대신 예산 확정 화면으로 강제 이동한다(2026-09-12, `budget/proposed` 시안·예산 미설정 배너는 쓰지 않음). 확정액 0 봉투는 잔여율이 없어 빈 트랙이고 지출이 있으면 초과 색·금액 |
| `AccountCard` | `features/account/components/AccountCard.tsx` | `View`(`bg-primary rounded-lg`) | `default` `selected` — 킷 `Card Bank / 1`을 단색 사각형으로 |
| `TransactionRow` | `features/account/components/TransactionRow.tsx` | `Text`, `Badge` | `deposit` `withdrawal` `pending` |
| `PinPad` | `features/auth/components/PinPad.tsx` | `Button` | 6자리, 셔플 옵션 |

컴포넌트가 아직 코드에 없으면 위 이름과 variant를 그대로 사용해 만든다. 이름을 바꿔야 하면 Pencil을 먼저 바꾸고 이 표와 `design-map.json`을 동기화한다.

## 6. 화면 패턴

- 화면 제목은 `text-h1` 하나. 뒤로가기는 플랫폼 기본 헤더 또는 좌상단 아이콘 버튼(`accessibilityLabel="뒤로"`).
- 하단 탭은 KeyFin 기준 4개(홈·자산·예산·마이, `TabBar`). 리포트 탭은 구현하지 않기로 해 2026-09-23 뺐다. 핵심 액션은 각 탭 화면 안에 둔다.
- 홈은 tint 배경(`bg-background`). 헤더는 `px-6 py-4`, 좌측에 `text-caption text-muted-foreground` "환영합니다"와 `text-h2` 인사말("{이름}님, 안녕하세요!"), 우측에 코인 배지(`bg-accent rounded-full`, 노란 원 + `text-label tabular-nums`)와 상점 버튼(40 원형 `bg-accent`, 우상단 배지 `bg-destructive`). 본문은 방 씬이 화면 폭 가득(좌우 여백 없음, 편집 화면과 같은 크기)이고 그 아래에는 아무것도 두지 않는다(사용자 결정 2026-09-15 — 방이 곧 대시보드). 예산 카드(`BudgetCard`)는 홈 본문에서 빠져 벽의 리스트(보드)를 탭하면 아래서 올라오는 예산 시트(`BudgetSheet`: 기간·요약 + 예산 카드 + 봉투별 남은 금액 + 예산 탭 링크)에만 있다. 캘린더 탭은 씬 안 팝오버 그대로.
- 이체 플로우는 `받는 사람 → 금액 → 확인 → 인증(PIN/생체) → 완료`의 5단계를 넘지 않는다. 확인 화면은 금액을 `text-amount-lg`로, 받는 사람·계좌를 마스킹해 표시한다.
- 로딩은 스피너보다 `Skeleton`. 1초 이상 걸리는 작업에만 진행 표시.
- 오류는 필드 근처에 원인 + 해결 방법. 재시도 버튼은 중복 요청을 막는다.
- 민감 정보(계좌번호 전체, 카드번호)는 기본 마스킹, 명시적 "보기" 액션으로만 노출.

## 7. 동기화 섹션 (Pencil이 원천 — `pencil-design` 절차 C가 갱신)

| 항목 | 값 |
|---|---|
| 확정 원천 | `design.pen`(Pencil) — 2026-08-30 Figma UI 킷 붙여넣기(킷 원본 프레임 17개는 참고 자료) + 토큰 기준 `Color style / tokens`·`Text style / tokens` 프레임, 구현 기준 아트보드 `home`·`home/dark`. 문서 변수 51개 = 시맨틱 색 35(라이트/다크) + white/black + radius-* + size-* + `$font-sans`(Pretendard — Pencil은 Google 폰트만 렌더해 캔버스는 폴백 서체로 보임) |
| 토큰 동기화 | `pnpm tokens:sync` = `scripts/sync-pen-tokens.cjs`(design.pen 변수 → tokens.json, 같은 hex는 프리미티브 참조) → `scripts/sync-tokens.cjs`(→ tailwind/global.css/theme.ts). `tokens:check`·`harness:check`·CI가 불일치를 잡는다 |
| 마지막 동기화 | `tokens.json` `$source.pencilSyncedAt` |
| 구현 전 대조 | `design/design-map.json`의 Pencil 노드 id → MCP `Get`·`TakeScreenshot` (`pencil-design` 절차 B) |
| Pencil 변수에 없는 토큰 | `radius.full`, 타이포 13종, 모션, 그림자 — 코드 전용, 승인 후 `tokens.json`에서 직접 관리 |
| Figma 내보내기(선택) | `scripts/figma/` 로컬 플러그인(`pnpm figma:build` → Figma 데스크톱 `Import plugin from manifest…`). design.pen `P0 화면`·`P0 화면 초안` 프레임(`SCREEN_IDS`) + tokens.json → Variables·Styles·프레임. **출력물이며 코드는 Figma를 읽지 않는다** |
