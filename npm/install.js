#!/usr/bin/env node
// install.js — postinstall hook for the skills-registry npm package.
//
// Downloads the matching prebuilt Go binary from GitHub Releases. If this
// step is skipped (e.g. `npm install --ignore-scripts`) or fails (offline,
// proxy), run.js falls back to downloading on first invocation, so the
// package still works. We therefore never hard-fail the install here.

"use strict";

const { downloadBinary, isInstalled, assetName } = require("./lib/binary");

async function main() {
  if (isInstalled()) {
    return;
  }
  try {
    await downloadBinary();
  } catch (err) {
    // Non-fatal: defer to the first-run fallback in run.js.
    console.warn(
      `skills-registry: could not download ${assetName()} during install ` +
        `(${err.message}). It will be fetched on first run.`
    );
  }
}

main();
