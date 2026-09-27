#!/usr/bin/env node
/**
 * scripts/figma/code.js 를 Figma 없이 실행하는 스모크 테스트.
 *
 *   node scripts/figma/smoke.cjs            # Pro 플랜처럼 컬렉션에 dark 모드 추가 가능
 *   STARTER=1 node scripts/figma/smoke.cjs  # Starter 플랜처럼 addMode 실패 → color/dark 컬렉션 폴백
 *
 * Figma Plugin API의 부분 집합을 흉내 내는 목(mock)이라 렌더링 결과는 검증하지 못한다.
 * 잡는 것: 정의되지 않은 API 호출, 서체 미로드 상태에서 텍스트 설정, 0 크기 resize, 예외로 인한 중단.
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const STARTER = process.env.STARTER === "1";
const code = fs.readFileSync(path.join(__dirname, "code.js"), "utf8");

const FONTS = [];
for (const family of ["Inter", "Poppins", "Pretendard", "Noto Sans KR", "Lato"]) {
  for (const style of ["Regular", "Medium", "SemiBold", "Bold", "Black", "Italic"]) FONTS.push({ fontName: { family, style } });
}
const loadedFonts = new Set();
const fontKey = (f) => `${f.family}/${f.style}`;

let nextId = 1;
const stats = { created: {}, warnings: [], notify: [], closed: null, groups: 0, svg: 0 };
const count = (type) => (stats.created[type] = (stats.created[type] || 0) + 1);

class Node {
  constructor(type) {
    this.type = type;
    this.id = `${nextId++}:${type}`;
    this.name = type;
    this.children = [];
    this.parent = null;
    this.x = 0;
    this.y = 0;
    this.width = 100;
    this.height = 100;
    this.rotation = 0;
    this.fills = [];
    this.strokes = [];
    this.effects = [];
    this.opacity = 1;
    this.visible = true;
    this.pluginData = {};
    this.removed = false;
    count(type);
  }
  get relativeTransform() {
    const r = (this.rotation * Math.PI) / 180;
    return [
      [Math.cos(r), -Math.sin(r), this.x],
      [Math.sin(r), Math.cos(r), this.y],
    ];
  }
  set relativeTransform(m) {
    if (!Array.isArray(m) || m.length !== 2 || m[0].length !== 3) throw new Error("relativeTransform 형식 오류");
    this.x = m[0][2];
    this.y = m[1][2];
  }
  appendChild(child) {
    if (child.removed) throw new Error(`삭제된 노드를 추가: ${child.name}`);
    if (child.parent) child.parent.children = child.parent.children.filter((c) => c !== child);
    child.parent = this;
    this.children.push(child);
  }
  insertChild(index, child) {
    this.appendChild(child);
    this.children.pop();
    this.children.splice(index, 0, child);
  }
  resize(w, h) {
    if (!(w >= 0.01) || !(h >= 0.01)) throw new Error(`resize 값 오류 (${this.name}): ${w} × ${h}`);
    this.width = w;
    this.height = h;
  }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this);
    this.removed = true;
  }
  setPluginData(key, value) {
    this.pluginData[key] = value;
  }
  setExplicitVariableModeForCollection() {}
  async setTextStyleIdAsync(id) {
    this.textStyleId = id;
  }
}
class TextNode extends Node {
  constructor() {
    super("TEXT");
    this._font = { family: "Inter", style: "Regular" };
    this._chars = "";
    this.textAutoResize = "WIDTH_AND_HEIGHT";
  }
  get fontName() {
    return this._font;
  }
  set fontName(f) {
    if (!loadedFonts.has(fontKey(f))) throw new Error(`서체 미로드 상태에서 fontName 설정: ${fontKey(f)}`);
    this._font = f;
  }
  get characters() {
    return this._chars;
  }
  set characters(v) {
    if (!loadedFonts.has(fontKey(this._font))) throw new Error(`서체 미로드 상태에서 characters 설정: ${fontKey(this._font)}`);
    if (typeof v !== "string") throw new Error("characters는 문자열이어야 합니다");
    this._chars = v;
    this.width = Math.max(1, v.length * 7);
    this.height = 16;
  }
}

function makePage(name) {
  const page = new Node("PAGE");
  page.name = name;
  return page;
}
const pages = [makePage("Page 1")];
let currentPage = pages[0];

const collections = [];
const figma = {
  root: { children: pages },
  get currentPage() {
    return currentPage;
  },
  viewport: { scrollAndZoomIntoView(nodes) { if (!Array.isArray(nodes)) throw new Error("scrollAndZoomIntoView 인자 오류"); } },
  notify(message) { stats.notify.push(message); },
  closePlugin(message) { stats.closed = message === undefined ? "ok" : message; },
  async loadAllPagesAsync() {},
  async setCurrentPageAsync(page) { currentPage = page; },
  createPage() { const p = makePage("Page"); pages.push(p); return p; },
  base64Decode(data) { if (typeof data !== "string" || !data.length) throw new Error("base64Decode 인자 오류"); return new Uint8Array(Buffer.from(data, "base64")); },
  createImage(bytes) {
    if (!(bytes instanceof Uint8Array)) throw new Error("createImage 인자는 Uint8Array");
    const png = bytes[0] === 0x89 && bytes[1] === 0x50;
    const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8;
    if (!png && !jpeg) throw new Error("PNG/JPEG가 아닌 이미지");
    count("IMAGE");
    return { hash: `img${nextId++}` };
  },
  createFrame() { const n = new Node("FRAME"); n.layoutMode = "NONE"; n.clipsContent = true; currentPage.appendChild(n); return n; },
  createRectangle() { const n = new Node("RECTANGLE"); currentPage.appendChild(n); return n; },
  createEllipse() { const n = new Node("ELLIPSE"); currentPage.appendChild(n); return n; },
  createText() { const n = new TextNode(); currentPage.appendChild(n); return n; },
  createNodeFromSvg(svg) {
    stats.svg++;
    // FAIL_EVERY=n 이면 n번째 SVG마다 실패시켜 노드 단위 try/catch·Import log 경로를 검증한다
    if (process.env.FAIL_EVERY && stats.svg % Number(process.env.FAIL_EVERY) === 0) throw new Error(`(모의) SVG 가져오기 실패 #${stats.svg}`);
    if (!/^<svg[\s>]/.test(svg) || !svg.includes("</svg>")) throw new Error("SVG 형식 오류");
    const wrapper = new Node("FRAME");
    wrapper.name = "svg";
    currentPage.appendChild(wrapper);
    const shapes = svg.match(/<(path|circle|rect|line|polyline|polygon|ellipse)\b[^>]*\/>/g) || [];
    for (const p of shapes) {
      const v = new Node("VECTOR");
      if (p.startsWith("<path")) {
        const d = (p.match(/\sd="([^"]*)"/) || [])[1];
        if (d === undefined) throw new Error("path에 d 속성이 없습니다");
        const nums = (d.match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
        v.width = nums.length > 1 ? Math.max(0.01, Math.max(...nums.filter((_, i) => i % 2 === 0)) - Math.min(0, ...nums.filter((_, i) => i % 2 === 0))) : 1;
        v.height = nums.length > 1 ? Math.max(0.01, Math.max(...nums.filter((_, i) => i % 2 === 1)) - Math.min(0, ...nums.filter((_, i) => i % 2 === 1))) : 1;
      } else {
        v.width = 10;
        v.height = 10;
      }
      if (/\sstroke="(?!none)/.test(p) || /stroke="currentColor"|stroke="#/.test(svg.slice(0, svg.indexOf(">")))) v.strokes = [{ type: "SOLID" }];
      if (/\sfill="(?!none)/.test(p)) v.fills = [{ type: "SOLID" }];
      wrapper.appendChild(v);
    }
    return wrapper;
  },
  group(nodes, parent, index) {
    if (!nodes.length) throw new Error("빈 그룹");
    stats.groups++;
    const g = new Node("GROUP");
    const absX = (n) => n.x + (n.parent && n.parent.type !== "PAGE" ? absX(n.parent) : 0);
    const absY = (n) => n.y + (n.parent && n.parent.type !== "PAGE" ? absY(n.parent) : 0);
    const abs = nodes.map((n) => ({ n, x: absX(n), y: absY(n) }));
    if (index === undefined) parent.appendChild(g);
    else parent.insertChild(index, g);
    for (const { n, x, y } of abs) {
      g.appendChild(n);
      n.x = x - absX(parent) - g.x;
      n.y = y - absY(parent) - g.y;
    }
    g.x = Math.min(...abs.map((a) => a.x)) - (parent.type === "PAGE" ? 0 : absX(parent));
    g.y = Math.min(...abs.map((a) => a.y)) - (parent.type === "PAGE" ? 0 : absY(parent));
    g.width = Math.max(1, ...nodes.map((n) => n.x + n.width));
    g.height = Math.max(1, ...nodes.map((n) => n.y + n.height));
    return g;
  },
  async listAvailableFontsAsync() { return FONTS; },
  async loadFontAsync(name) {
    if (!FONTS.some((f) => f.fontName.family === name.family && f.fontName.style === name.style)) throw new Error(`서체 없음: ${fontKey(name)}`);
    loadedFonts.add(fontKey(name));
  },
  createPaintStyle() { const s = { id: `S${nextId++}` }; count("PAINT_STYLE"); return s; },
  createTextStyle() { const s = { id: `T${nextId++}` }; count("TEXT_STYLE"); return s; },
  variables: {
    createVariableCollection(name) {
      const c = { name, modes: [{ modeId: `m${nextId++}`, name: "Mode 1" }], renameMode(id, n) { const m = c.modes.find((x) => x.modeId === id); if (!m) throw new Error("모드 없음"); m.name = n; }, addMode(n) { if (STARTER) throw new Error("이 플랜은 모드 1개만 허용"); const id = `m${nextId++}`; c.modes.push({ modeId: id, name: n }); return id; } };
      collections.push(c);
      return c;
    },
    createVariable(name, collection, type) {
      count("VARIABLE");
      return { id: `V${nextId++}`, name, type, values: {}, setValueForMode(modeId, v) { if (!collection.modes.some((m) => m.modeId === modeId)) throw new Error(`모드 없음: ${modeId}`); this.values[modeId] = v; } };
    },
    setBoundVariableForPaint(paint, field, variable) {
      if (!variable || !variable.id) throw new Error("변수 없음");
      return { ...paint, boundVariables: { [field]: { type: "VARIABLE_ALIAS", id: variable.id } } };
    },
  },
};

const consoleMock = {
  log: () => {},
  warn: (...args) => stats.warnings.push(args.map((a) => (typeof a === "string" ? a : a && a.message ? a.message : JSON.stringify(a))).join(" ")),
  error: (...args) => stats.warnings.push("ERROR " + args.map((a) => (a && a.stack) || String(a)).join(" ")),
};

async function run() {
  const context = vm.createContext({ figma, console: consoleMock, Promise, Math, JSON, String, Number, Boolean, Array, Object, Map, Set, parseInt, parseFloat, Error });
  vm.runInContext(code, context, { filename: "code.js" });
  const started = Date.now();
  while (stats.closed === null) {
    if (Date.now() - started > 60000) throw new Error("플러그인이 60초 안에 끝나지 않았습니다");
    await new Promise((r) => setTimeout(r, 20));
  }
  const screens = pages.find((p) => p.name === "Screens");
  const foundations = pages.find((p) => p.name === "Foundations");
  const tally = {};
  const walk = (n) => { tally[n.type] = (tally[n.type] || 0) + 1; for (const c of n.children) walk(c); };
  if (screens) for (const c of screens.children) walk(c);
  const top = screens ? screens.children.map((c) => `${c.name}@${Math.round(c.x)},${Math.round(c.y)} ${Math.round(c.width)}×${Math.round(c.height)}`) : [];
  const orphanText = [];
  if (screens) Get(screens, (n) => n.type === "TEXT" && n.characters.length === 0 && orphanText.push(n.name));
  console.log(`플랜: ${STARTER ? "Starter(폴백)" : "다중 모드"} · 종료: ${stats.closed}`);
  console.log(`페이지: ${pages.map((p) => p.name).join(", ")} · Foundations 프레임 ${foundations ? foundations.children.length : 0}`);
  console.log(`Screens 최상위 ${top.length}개:\n  ${top.join("\n  ")}`);
  console.log(`Screens 노드: ${JSON.stringify(tally)}`);
  console.log(`생성 호출: ${JSON.stringify(stats.created)} · SVG ${stats.svg} · 그룹 ${stats.groups} · 컬렉션 ${collections.map((c) => `${c.name}[${c.modes.map((m) => m.name).join("/")}]`).join(", ")}`);
  console.log(`알림: ${stats.notify.join(" | ")}`);
  const errors = stats.warnings.filter((w) => w.startsWith("ERROR"));
  const substitutions = stats.warnings.filter((w) => w.includes("서체 대체"));
  const log = screens ? screens.children.find((c) => c.name === "Import log") : null;
  console.log(`경고 ${stats.warnings.length}건 (서체 대체 ${substitutions.length}, 빈 텍스트 ${orphanText.length}) · 노드 실패 ${errors.length}건${log ? ` · Import log ${log.characters.split("\n").length}줄` : ""}`);
  for (const w of stats.warnings.filter((w) => !w.includes("서체 대체")).slice(0, 8)) console.log("  -", w.slice(0, 200));
  const injected = Boolean(process.env.FAIL_EVERY);
  if (stats.closed !== "ok" || (errors.length && !injected) || (injected && (!errors.length || !log))) {
    console.error("실패");
    process.exit(1);
  }
}
function Get(node, visit) {
  visit(node);
  for (const c of node.children) Get(c, visit);
}
run().catch((error) => {
  console.error(error);
  process.exit(1);
});
