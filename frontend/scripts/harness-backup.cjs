#!/usr/bin/env node
// 하네스·디자인 원천을 저장소 밖으로 복사한다.
// 이 경로들은 .gitignore 대상이라 git 이 백업해 주지 않는다. 브랜치 전환·pull 로
// 통째로 사라진 적이 있어(2026-09-08) 로컬 사본을 따로 둔다.
// bash/rsync 의존 없이 node만으로 동작하므로 OS에 관계없이 같은 결과를 낸다.
const fs = require("fs");
const os = require("os");
const path = require("path");

process.chdir(path.join(__dirname, ".."));

const ROOT = process.env.KEYFIN_HARNESS_BACKUP || path.join(os.homedir(), "keyfin-harness-backup");
const CURRENT = path.join(ROOT, "current");
const PREV = path.join(ROOT, "prev");

// .claude/ 는 .agents/ 의 미러라 harness:sync 로 다시 만들 수 있어 백업하지 않는다.
const TARGETS = [".agents", "docs", "AGENTS.md", "CLAUDE.md", "skills-lock.json", "design.pen"];

// 원본이 이미 비어 있는데 백업을 덮으면 멀쩡한 사본을 잃는다. 그래서 먼저 막는다.
const missing = TARGETS.filter((t) => !fs.existsSync(t));
if (missing.length) {
  console.error("백업 중단: 원본이 없다 → " + missing.join(", "));
  console.error("파일이 사라진 상태라면 백업이 아니라 `pnpm harness:restore` 가 필요하다.");
  process.exit(1);
}

// 직전 백업을 한 세대 남긴다.
fs.rmSync(PREV, { recursive: true, force: true });
if (fs.existsSync(CURRENT)) fs.renameSync(CURRENT, PREV);
fs.mkdirSync(CURRENT, { recursive: true });

let files = 0;
let bytes = 0;
for (const t of TARGETS) {
  const dst = path.join(CURRENT, t);
  fs.cpSync(t, dst, { recursive: true });
  for (const f of walk(dst)) {
    files++;
    bytes += fs.statSync(f).size;
  }
}

fs.writeFileSync(
  path.join(CURRENT, "BACKUP-INFO.txt"),
  [
    "KeyFin 프론트 하네스 백업",
    "생성: " + new Date().toISOString(),
    "원본: " + process.cwd(),
    "파일: " + files + "개 / " + (bytes / 1048576).toFixed(1) + "MB",
    "",
    "되돌리기: pnpm harness:restore",
    "직전 세대: " + PREV,
  ].join("\n") + "\n"
);

console.log(`백업 완료: ${files}개 파일 / ${(bytes / 1048576).toFixed(1)}MB`);
console.log("위치: " + CURRENT);
if (fs.existsSync(PREV)) console.log("직전 백업은 prev/ 로 보관했다.");

function* walk(p) {
  const st = fs.statSync(p);
  if (st.isFile()) {
    yield p;
    return;
  }
  for (const e of fs.readdirSync(p)) yield* walk(path.join(p, e));
}
