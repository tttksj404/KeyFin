#!/usr/bin/env node
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.resolve(__dirname, "../..");
const run = (script, extraEnv = {}) => {
  const result = spawnSync(process.execPath, [path.join(__dirname, script)], {
    cwd: root,
    env: { ...process.env, STARTER: undefined, FAIL_EVERY: undefined, ...extraEnv },
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
};

run("../figma/build-plugin.cjs");
run("smoke.cjs");
run("smoke.cjs", { STARTER: "1" });
run("smoke.cjs", { FAIL_EVERY: "97" });
