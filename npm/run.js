#!/usr/bin/env node
// run.js — bin launcher for the skills-registry npm package.
//
// Execs the prebuilt Go binary, downloading it first if the postinstall
// hook was skipped (`--ignore-scripts`) or failed. stdio is inherited so
// the Charmbracelet TUI renders normally and exit codes propagate.

"use strict";

const { spawnSync } = require("child_process");
const { binaryPath, downloadBinary, isInstalled, assetName } = require("./lib/binary");

async function ensureBinary() {
  if (isInstalled()) {
    return;
  }
  process.stderr.write(`skills-registry: downloading ${assetName()}…\n`);
  await downloadBinary();
}

async function main() {
  try {
    await ensureBinary();
  } catch (err) {
    process.stderr.write(`skills-registry: ${err.message}\n`);
    process.exit(1);
  }

  const result = spawnSync(binaryPath(), process.argv.slice(2), {
    stdio: "inherit",
  });

  if (result.error) {
    process.stderr.write(`skills-registry: ${result.error.message}\n`);
    process.exit(1);
  }
  // Mirror signal-based termination where possible; otherwise pass exit code.
  if (result.signal) {
    process.kill(process.pid, result.signal);
    return;
  }
  process.exit(result.status === null ? 1 : result.status);
}

main();
