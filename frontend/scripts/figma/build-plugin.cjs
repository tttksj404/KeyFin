#!/usr/bin/env node
/**
 * design/tokens.json + lucide 아이콘 → scripts/figma/code.js (Figma 로컬 플러그인) 생성
 *
 *   node scripts/figma/build-plugin.cjs
 *
 * 사용: Figma 데스크톱 앱 → Plugins → Development → Import plugin from manifest… → scripts/figma/manifest.json 선택 → 실행.
 * 편집 권한이 있는 파일이면 Starter 플랜에서도 동작한다(모드가 1개로 제한되면 다크 값은 color/dark 컬렉션으로 생성).
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
const tokens = JSON.parse(fs.readFileSync(path.join(ROOT, "design", "tokens.json"), "utf8"));
const MODES = tokens.$modes ?? ["light", "dark"];

function getByPath(obj, dotted) {
  return dotted.split(".").reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}
function resolve(value, depth = 0) {
  if (depth > 10) throw new Error(`토큰 참조가 너무 깊습니다: ${JSON.stringify(value)}`);
  if (typeof value === "string") {
    const m = value.match(/^\{(.+)\}$/);
    if (!m) return value;
    const target = getByPath(tokens, m[1]);
    if (target === undefined) throw new Error(`참조를 찾을 수 없습니다: ${value}`);
    return resolve(target.$value !== undefined ? target.$value : target, depth + 1);
  }
  if (value && typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) out[k] = resolve(v, depth + 1);
    return out;
  }
  return value;
}
function walk(group, prefix, visit) {
  for (const [key, node] of Object.entries(group)) {
    if (key.startsWith("$")) continue;
    if (node && typeof node === "object" && "$value" in node) visit([...prefix, key], node);
    else if (node && typeof node === "object") walk(node, [...prefix, key], visit);
  }
}

const colors = Object.fromEntries(MODES.map((m) => [m, {}]));
walk(tokens.semantic.color, [], (parts, node) => {
  const raw = resolve(node.$value);
  for (const m of MODES) colors[m][parts.join("-")] = (typeof raw === "object" ? raw[m] : raw).toUpperCase();
});
for (const fixed of ["white", "black"]) {
  const v = resolve(tokens.primitive.color[fixed].$value).toUpperCase();
  for (const m of MODES) colors[m][fixed] = v;
}
const typography = {};
walk(tokens.semantic.typography, [], (parts, node) => {
  const t = resolve(node.$value);
  typography[parts.join("-")] = { fontSize: t.fontSize, lineHeight: t.lineHeight, fontWeight: Number(t.fontWeight), letterSpacing: t.letterSpacing };
});
const dims = (group) => {
  const out = {};
  walk(group, [], (parts, node) => {
    const v = resolve(node.$value);
    if (typeof v === "number" && v < 9999) out[parts.join("-")] = v;
  });
  return out;
};

const samples = {
  display: "온보딩 헤드라인 Display",
  "amount-lg": "1,250,000원",
  "amount-md": "3,469,520원",
  "amount-sm": "-30,000원 / +1,250,000원",
  h1: "화면 제목 Title 1",
  h2: "섹션 제목 Title 2",
  h3: "카드 제목 Title 3",
  "body-lg": "강조 본문 Body large",
  body: "기본 본문 Body 2 — 계좌를 연결하면 잔액을 여기서 볼 수 있어요.",
  "body-sm": "보조 설명 Body 3 — 연결 상태를 확인한 뒤 다시 시도해 주세요.",
  label: "입력 라벨 · 탭 · 카테고리명",
  caption: "날짜 · 상태 · 법적 고지 Caption 2",
  button: "이체하기 Button",
};

// ---------- lucide 아이콘 → SVG (design.pen의 icon 노드가 쓰는 이름만) ----------
const iconsDir = path.join(ROOT, "node_modules", "lucide-react-native", "dist", "esm", "icons");
function loadLucideIcon(name) {
  const file = path.join(iconsDir, `${name}.mjs`);
  if (!fs.existsSync(file)) throw new Error(`lucide 아이콘을 찾을 수 없습니다: ${name}`);
  const src = fs.readFileSync(file, "utf8");
  const m = src.match(/createLucideIcon\("[^"]+",\s*(\[[\s\S]*?\])\);/);
  if (!m) throw new Error(`아이콘 파싱 실패: ${name}`);
  const nodes = new Function(`return ${m[1]}`)();
  const body = nodes
    .map(([tag, attrs]) => {
      const attrText = Object.entries(attrs)
        .filter(([k]) => k !== "key")
        .map(([k, v]) => `${k}="${v}"`)
        .join(" ");
      return `<${tag} ${attrText}/>`;
    })
    .join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="__SIZE__" height="__SIZE__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
}

// ---------- design.pen → 최상위 프레임(SCREEN_IDS) ----------
// design.pen은 평문 JSON이다. 최상위 프레임을 id로 찾아 서브트리를 그대로 심고, 플러그인의 buildPenNode가 Figma 노드로 변환한다.
// 색 변수(`$primary` …)는 치환하지 않고 남겨 플러그인이 Figma 변수에 바인딩하게 하고, 숫자·문자열 변수는 값으로 치환한다.
const PEN_PATH = path.join(ROOT, "design.pen");
const SCREEN_IDS = [
  "L36Q0u", // P0 화면 — 구현 기준 아트보드(흐름 순 배치)
  "n3r9i", // P0 화면 초안 — 사용자 스냅샷 복사본
];
const pen = JSON.parse(fs.readFileSync(PEN_PATH, "utf8"));
const penTop = new Map(pen.children.map((n) => [n.id, n]));
const penById = new Map();
const indexPenNodes = (node) => {
  penById.set(node.id, node);
  for (const child of node.children ?? []) indexPenNodes(child);
};
pen.children.forEach(indexPenNodes);

// 서체 원천은 tokens.json이다. Pencil의 `$font-sans`는 캔버스 렌더용 대체값일 수 있으므로 토큰 값(Pretendard)으로 치환한다.
const fontSansToken = (tokens.primitive?.fontFamily?.sans ?? tokens.semantic?.fontFamily?.sans)?.$value;
if (typeof fontSansToken !== "string") throw new Error("tokens.json에서 fontFamily.sans 토큰을 찾을 수 없습니다");
const FONT_SANS = resolve(fontSansToken);

function penVariable(name) {
  if (name === "font-sans") return FONT_SANS;
  const def = pen.variables?.[name];
  if (Array.isArray(def.value)) {
    const light = def.value.find((v) => !v.theme || v.theme.mode === "light") ?? def.value[0];
    return light.value;
  }
  return def.value;
}
// `$name`은 그 이름의 문서 변수가 있을 때만 치환한다(`$3.469.52` 같은 텍스트 내용은 그대로 둔다). 색 변수는 참조를 유지한다.
function resolvePen(value, depth = 0) {
  if (depth > 10) throw new Error(`design.pen 변수 참조가 너무 깊습니다: ${JSON.stringify(value)}`);
  if (typeof value === "string" && value.startsWith("$") && pen.variables?.[value.slice(1)]) {
    if (pen.variables[value.slice(1)].type === "color") return value;
    return resolvePen(penVariable(value.slice(1)), depth + 1);
  }
  if (Array.isArray(value)) return value.map((v) => resolvePen(v, depth + 1));
  if (value && typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) out[k] = resolvePen(v, depth + 1);
    return out;
  }
  return value;
}
const round = (v) => (typeof v === "number" ? Math.round(v * 1000) / 1000 : v);
// 플러그인에 필요한 속성만 남기고 값은 소수 3자리로 줄인다.
const KEEP = [
  "type", "id", "name", "x", "y", "width", "height", "rotation", "flipX", "flipY", "opacity", "enabled", "clip",
  "fill", "stroke", "strokeWidth", "strokeAlignment", "strokeLinecap", "strokeLinejoin", "effect", "cornerRadius",
  "geometry", "fillRule", "viewBox", "innerRadius", "startAngle", "sweepAngle",
  "content", "textGrowth", "fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing", "textAlign", "textAlignVertical", "underline", "strikethrough",
  "layout", "gap", "padding", "justifyContent", "alignItems", "layoutPosition", "theme", "library", "icon",
];
function compactPen(node) {
  const out = {};
  for (const key of KEEP) {
    if (node[key] === undefined) continue;
    let v = ["content", "name", "geometry", "id"].includes(key) ? node[key] : resolvePen(node[key]);
    if (key === "rotation" && Math.abs(v) < 0.001) continue;
    if (typeof v === "number") v = round(v);
    else if (Array.isArray(v)) v = v.map(round);
    out[key] = v;
  }
  if (node.children) out.children = node.children.map(compactPen);
  return out;
}
function resolvePenRefs(node, stack = []) {
  if (node.type !== "ref") {
    return { ...node, children: node.children?.map((child) => resolvePenRefs(child, stack)) };
  }
  if (stack.includes(node.ref)) throw new Error(`컴포넌트 인스턴스 순환 참조: ${node.id}`);
  const source = penById.get(node.ref);
  if (!source) throw new Error(`컴포넌트 원본을 찾을 수 없습니다: ${node.ref}`);
  const resolved = JSON.parse(JSON.stringify(source));
  const descendants = node.descendants ?? {};
  const applyOverrides = (child) => {
    const override = descendants[child.id];
    return {
      ...child,
      ...(override ?? {}),
      children: child.children?.map(applyOverrides),
    };
  };
  const instance = applyOverrides(resolved);
  instance.id = node.id;
  instance.name = node.name ?? instance.name;
  delete instance.reusable;
  return resolvePenRefs(instance, [...stack, node.ref]);
}
// 없는 id를 조용히 건너뛰거나 문서 전체로 대체하면 옛 화면·엉뚱한 범위가 내보내지므로 멈춘다.
const missingScreens = SCREEN_IDS.filter((id) => !penTop.has(id));
if (missingScreens.length) {
  const available = pen.children.map((n) => `${n.id}(${n.name})`).join(", ");
  throw new Error(`design.pen 최상위에 없는 SCREEN_IDS: ${missingScreens.join(", ")}\n  최상위 노드: ${available}`);
}
const penScreens = SCREEN_IDS.map((id) => compactPen(resolvePenRefs(penTop.get(id))));
// Pencil 캔버스 좌표를 그대로 옮기되 원점만 화면들의 좌상단으로 맞춘다
const origin = { x: Math.min(...penScreens.map((s) => s.x)), y: Math.min(...penScreens.map((s) => s.y)) };
for (const s of penScreens) {
  s.x = round(s.x - origin.x);
  s.y = round(s.y - origin.y);
}
const penNodeCount = (n) => 1 + (n.children ?? []).reduce((acc, c) => acc + penNodeCount(c), 0);
const icons = {};
const collectIcons = (n) => {
  if (n.type === "icon") {
    if (n.library !== "lucide") throw new Error(`lucide 외 아이콘 라이브러리는 지원하지 않습니다: ${n.library}/${n.icon} (${n.id})`);
    icons[n.icon] ??= loadLucideIcon(n.icon);
  }
  for (const c of n.children ?? []) collectIcons(c);
};
penScreens.forEach(collectIcons);
// 이미지 fill은 url(design.pen 기준 상대경로)의 파일을 base64로 심는다. 플러그인은 networkAccess가 없어 파일을 직접 읽지 못한다.
const images = {};
const collectImages = (n) => {
  for (const f of [].concat(n.fill ?? [])) {
    if (!f || f.type !== "image" || !f.url || images[f.url]) continue;
    const file = path.resolve(path.dirname(PEN_PATH), f.url);
    if (!fs.existsSync(file)) throw new Error(`이미지 파일을 찾을 수 없습니다: ${f.url} (${n.id})`);
    images[f.url] = fs.readFileSync(file).toString("base64");
  }
  for (const c of n.children ?? []) collectImages(c);
};
penScreens.forEach(collectImages);
const SCREENS = { source: "design.pen", screens: penScreens };

const TOKENS = { colors, typography, radius: dims(tokens.semantic.radius), size: dims(tokens.semantic.size), samples };
const template = fs.readFileSync(path.join(__dirname, "code.template.js"), "utf8");
// 치환 문자열의 `$&`·`$'` 같은 패턴이 해석되지 않게 함수로 넘긴다.
const code = template
  .replace("__TOKENS__", () => JSON.stringify(TOKENS, null, 2))
  .replace("__ICONS__", () => JSON.stringify(icons, null, 2))
  .replace("__IMAGES__", () => JSON.stringify(images))
  .replace("__SCREENS__", () => JSON.stringify(SCREENS));
fs.writeFileSync(path.join(__dirname, "code.js"), code);
const totalNodes = penScreens.reduce((acc, s) => acc + penNodeCount(s), 0);
console.log(
  `생성: scripts/figma/code.js (색 ${Object.keys(colors.light).length} × ${MODES.length}모드, 타이포 ${Object.keys(typography).length}, 아이콘 ${Object.keys(icons).length}, 이미지 ${Object.keys(images).length}, 화면 ${penScreens.length}개 · 노드 ${totalNodes}개, ${Math.round(code.length / 1024)}KB)`
);
