#!/usr/bin/env node
// 하네스 무결성 검사: 미러 동기화, JSON 유효성, 스킬 잠금, 토큰 산출물 최신 여부
// bash 대신 node로 실행한다. Windows에서 WSL이 설치돼 있으면 pnpm이 띄우는 bash가
// WSL로 잡혀 node를 찾지 못하므로, 셸 의존 없이 어떤 OS에서도 동작하게 한다.
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

process.chdir(path.join(__dirname, ".."));
let fail = false;

/** 디렉터리 아래 모든 파일의 상대 경로 목록 (정렬) */
function listFiles(dir) {
  const out = [];
  const walk = (cur) => {
    for (const ent of fs.readdirSync(cur, { withFileTypes: true })) {
      const full = path.join(cur, ent.name);
      if (ent.isDirectory()) walk(full);
      else out.push(path.relative(dir, full).split(path.sep).join("/"));
    }
  };
  if (fs.existsSync(dir)) walk(dir);
  return out.sort();
}

/** diff -rq 와 같은 결과: 한쪽에만 있거나 내용이 다른 파일 목록 */
function diffDirs(a, b) {
  const fa = listFiles(a);
  const fb = listFiles(b);
  const sb = new Set(fb);
  const problems = [];
  for (const f of fa) {
    if (!sb.has(f)) problems.push(`Only in ${a}: ${f}`);
    else if (!fs.readFileSync(path.join(a, f)).equals(fs.readFileSync(path.join(b, f))))
      problems.push(`Files ${a}/${f} and ${b}/${f} differ`);
  }
  const sa = new Set(fa);
  for (const f of fb) if (!sa.has(f)) problems.push(`Only in ${b}: ${f}`);
  return problems;
}

function checkMirror(src, dst, limit) {
  console.log(`▶ ${src} ↔ ${dst}`);
  const problems = diffDirs(src, dst);
  if (problems.length === 0) {
    console.log("  OK");
  } else {
    console.log("  FAIL: 미러 불일치 (pnpm harness:sync)");
    for (const p of problems.slice(0, limit)) console.log(p);
    fail = true;
  }
}

/** node 하위 스크립트를 실행하고 종료 코드로 성공 여부를 돌려준다 */
function runNode(args) {
  const r = spawnSync(process.execPath, args, { stdio: "inherit" });
  return r.status === 0;
}

checkMirror(".agents/rules", ".claude/rules", Infinity);
checkMirror(".agents/skills", ".claude/skills", 20);

console.log("▶ design/*.json 파싱");
// design-map.json 은 로컬 보관(gitignore)이라 없을 수 있다. 있으면 형식만 검사한다.
for (const f of ["design/tokens.json", "design/design-map.json"]) {
  if (!fs.existsSync(f)) {
    console.log(`  건너뜀 ${f} (없음 — 로컬 전용 파일)`);
    continue;
  }
  try {
    JSON.parse(fs.readFileSync(f, "utf8"));
    console.log(`  OK ${f}`);
  } catch {
    console.log(`  FAIL: ${f} 파싱 오류`);
    fail = true;
  }
}

console.log("▶ design.pen ↔ tokens.json (Pencil 변수가 원천)");
if (!runNode(["scripts/sync-pen-tokens.cjs", "--check"])) fail = true;

console.log("▶ skills-lock.json 이 모든 스킬을 추적하는지");
{
  let lock = {};
  try {
    lock = JSON.parse(fs.readFileSync("skills-lock.json", "utf8"));
  } catch {
    console.log("  FAIL: skills-lock.json 파싱 오류");
    fail = true;
  }
  const skills = fs
    .readdirSync(".agents/skills", { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
  for (const name of skills) {
    if (lock.skills && lock.skills[name]) console.log(`  OK ${name}`);
    else {
      console.log(`  FAIL: skills-lock.json 에 ${name} 없음`);
      fail = true;
    }
  }
}

console.log("▶ 토큰 산출물 최신 여부");
if (!runNode(["scripts/sync-tokens.cjs", "--check"])) fail = true;

console.log("▶ 규칙 파일 frontmatter(paths)");
{
  let ok = true;
  const rules = fs
    .readdirSync(".agents/rules")
    .filter((f) => f.endsWith(".md"))
    .sort();
  for (const f of rules) {
    const rel = `.agents/rules/${f}`;
    // CRLF 체크아웃도 허용하도록 \r 은 제거하고 비교한다
    const lines = fs.readFileSync(rel, "utf8").split(/\r?\n/);
    const hasFrontmatter = lines[0] === "---";
    const hasPaths = lines.some((l) => l.startsWith("paths:"));
    if (!hasFrontmatter || !hasPaths) {
      console.log(`  FAIL: ${rel} 에 paths frontmatter 없음`);
      ok = false;
      fail = true;
    }
  }
  if (ok) console.log("  OK");
}

console.log("▶ design.pen 이미지 참조 ↔ design/images 파일");
{
  // .pen 파일의 image fill url은 그 .pen 파일 기준 상대경로다.
  // (1) url 없는 image fill = 붙여넣기 때 이미지가 안 들어온 것, (2) 파일이 없는 url,
  // (3) 어떤 .pen도 참조하지 않는 파일 = 고아 파일이 쌓이는 것을 막는다.
  const IMAGE_EXT = /\.(png|jpe?g|webp|gif|svg)$/i;
  const penFiles = ["design.pen"];
  if (fs.existsSync("design/pencil"))
    for (const f of fs.readdirSync("design/pencil")) if (f.endsWith(".pen")) penFiles.push(`design/pencil/${f}`);
  const referenced = new Set();
  const noUrl = [];
  const missing = [];
  for (const pen of penFiles) {
    let doc;
    try {
      doc = JSON.parse(fs.readFileSync(pen, "utf8"));
    } catch {
      console.log(`  FAIL: ${pen} 파싱 오류`);
      fail = true;
      continue;
    }
    const penDir = path.dirname(pen);
    const walk = (n, chain) => {
      if (!n || typeof n !== "object") return;
      for (const f of [].concat(n.fill || [])) {
        if (!f || typeof f !== "object" || f.type !== "image") continue;
        if (!f.url) {
          noUrl.push(`${pen}: ${chain.join(" > ")} (${n.id})`);
          continue;
        }
        if (/^(https?:|data:)/.test(f.url)) continue;
        const rel = path.normalize(path.join(penDir, f.url)).split(path.sep).join("/");
        referenced.add(rel);
        if (!fs.existsSync(rel)) missing.push(`${pen}: ${f.url} (${n.id})`);
      }
      for (const c of n.children || []) walk(c, [...chain, c.name || c.id]);
    };
    walk({ children: doc.children }, []);
  }
  const orphans = fs.existsSync("design/images")
    ? listFiles("design/images").filter((f) => IMAGE_EXT.test(f) && !referenced.has(`design/images/${f}`))
    : [];
  if (noUrl.length) {
    console.log(`  FAIL: url 없는 image fill ${noUrl.length}개 (이미지가 들어오지 않은 노드)`);
    for (const s of noUrl.slice(0, 10)) console.log(`    ${s}`);
    fail = true;
  }
  if (missing.length) {
    console.log(`  FAIL: 파일이 없는 이미지 참조 ${missing.length}개`);
    for (const s of missing.slice(0, 10)) console.log(`    ${s}`);
    fail = true;
  }
  if (orphans.length) {
    console.log(`  FAIL: 어떤 .pen도 참조하지 않는 파일 ${orphans.length}개 (design/images) — 삭제하거나 참조를 연결한다`);
    for (const s of orphans.slice(0, 10)) console.log(`    ${s}`);
    fail = true;
  }
  if (!noUrl.length && !missing.length && !orphans.length)
    console.log(`  OK 참조 ${referenced.size}개 파일, 고아 파일 없음`);
}

if (fail) {
  console.log();
  console.log("하네스 검사 실패");
  process.exit(1);
}
console.log();
console.log("하네스 검사 통과");
