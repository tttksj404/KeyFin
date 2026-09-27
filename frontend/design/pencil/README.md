# Pencil 대안 드래프트 (`design/pencil/`)

**메인 작업 파일은 리포 루트의 `design.pen`이며, 이 파일이 디자인의 확정 원천이다.** 에이전트는 `design.pen`이 에디터에 열려 있을 때만 Pencil MCP를 쓸 수 있다.

이 디렉토리(`design/pencil/`)는 메인 파일과 분리해 탐색할 대안 드래프트(`<flow>-<screen>.pen`)만 둔다. 확정되면 `design.pen`으로 옮기고 여기 파일은 히스토리로 남긴다.

## 확정 흐름

```
design.pen (Pencil: 변수 51개 + 아트보드)
   ├─ sync-pen-tokens.cjs ──▶ design/tokens.json ──sync-tokens.cjs──▶ tailwind.config.js · global.css · lib/theme.ts
   ├─ 구현 전 대조 (MCP Get · TakeScreenshot, design-map.json의 노드 id) ──▶ app/ features/ components/
   └─ (선택) pnpm figma:build ──▶ Figma  ← 공유·열람용 출력물. 코드는 Figma를 읽지 않는다
```

- 토큰 변경은 Pencil 변수(`SetVariables`) → `pnpm tokens:sync` 순서. `tokens:check`가 `design.pen`과 `tokens.json`의 불일치를 잡는다.
- Figma UI 킷은 2026-08-30 Pencil 앱에 붙여넣기로 가져왔다(킷 원본 프레임은 참고 자료). Figma에서 다시 읽어 오는 경로는 없다.

## 규약

- 아트보드 이름은 `design/design-map.json`의 `screens` 키와 같게 한다 (`home`, `transfer-confirm` 등). 다크 모드는 `home/dark`.
- 색·반경·크기·서체는 `design.pen` 문서 변수(`$primary`, `$radius-lg`, `$size-button-lg`, `$font-sans` …)만 참조한다. 변수 이름 = `tokens.json` 경로.
- 컴포넌트 이름은 `DESIGN.md` 5장의 인벤토리와 동일하게 짓는다.

## 에이전트 작업 절차

1. Pencil 에디터에서 루트의 `design.pen`을 연다.
2. `mcp__pencil__get_app_state` → `mcp__pencil__read_skill`.
3. `.agents/skills/pencil-design/SKILL.md`의 절차(A 드래프트 · B 대조 · C 토큰 동기화)를 따른다.
4. 확정되면 `design-map.json`에 노드 id를 기록한다.

`design.pen`은 평문 JSON이지만 3.8MB라 에이전트는 MCP로 읽고, 스크립트(`scripts/sync-pen-tokens.cjs`, `scripts/figma/build-plugin.cjs`)만 파일을 직접 읽는다.
