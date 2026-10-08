#!/usr/bin/env node
// web-ui-check — mechanical checks of a rendered web UI, and side-by-side
// comparison images against an approved baseline. It measures; it never judges
// how a page looks. Run by the `web_ui_check` OpenCode tool
// (../custom-tools/web_ui.ts) as a Node child process, since Playwright is not
// reliable inside the Bun plugin host.
//
//   web-ui-check capture --out DIR --page NAME=URL [--page NAME=URL ...]
//                        [--viewport 1440x900 --viewport 375x812]
//                        [--scheme light|dark|both] [--wait-for SELECTOR]
//                        [--ignore-console REGEX]
//                        [--focus-steps 25]
//   web-ui-check compare --baseline DIR --current DIR --out DIR
//
// Exit status: capture 0 = no failures, 1 = failures found; compare 0 = every
// pair compared, 1 = some pair could not be compared; 2 = usage or runtime error
// (a missing baseline directory included).

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const USAGE = `usage:
  web-ui-check capture --out DIR --page NAME=URL [--page NAME=URL ...]
                       [--viewport WxH ...] [--scheme light|dark|both]
                       [--wait-for SELECTOR]
                       [--ignore-console REGEX] [--focus-steps N]
  web-ui-check compare --baseline DIR --current DIR --out DIR`;

const DEFAULT_VIEWPORTS = ["1440x900", "375x812"];
const NAV_TIMEOUT = 30000;
const IDLE_TIMEOUT = 5000;
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const FAIL_IMPACTS = new Set(["critical", "serious"]);
const PIXEL_THRESHOLD = 32;

class UsageError extends Error {}

function parse(argv) {
  const [command, ...rest] = argv;
  if (command === "-h" || command === "--help") throw new UsageError("");
  const opts = { _: command, page: [], viewport: [] };
  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i];
    if (arg === "-h" || arg === "--help") throw new UsageError("");
    if (!arg.startsWith("--")) throw new UsageError(`unexpected argument: ${arg}`);
    const key = arg.slice(2);
    const value = rest[++i];
    if (value === undefined) throw new UsageError(`${arg} needs a value`);
    if (key === "page" || key === "viewport") opts[key].push(value);
    else opts[key] = value;
  }
  return opts;
}

function slug(text) {
  return text.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "page";
}

async function launch() {
  const { chromium } = await import("playwright");
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    if (/Executable doesn't exist/.test(String(error))) {
      throw new Error(
        "Playwright's browser is not installed. Run: " +
          "~/.config/opencode/node_modules/.bin/playwright install chromium-headless-shell",
      );
    }
    throw error;
  }
}

// --------------------------------------------------------------------------
// capture

function pages(opts) {
  if (!opts.page.length) throw new UsageError("capture needs at least one --page NAME=URL");
  const seen = new Set();
  return opts.page.map((spec) => {
    const at = spec.indexOf("=");
    if (at < 1) throw new UsageError(`--page must be NAME=URL: ${spec}`);
    const name = slug(spec.slice(0, at));
    const url = spec.slice(at + 1);
    if (!/^https?:\/\//.test(url)) throw new UsageError(`--page URL must be http(s): ${url}`);
    if (seen.has(name)) throw new UsageError(`duplicate page name: ${name}`);
    seen.add(name);
    return { name, url };
  });
}

function viewports(opts) {
  return (opts.viewport.length ? opts.viewport : DEFAULT_VIEWPORTS).map((spec) => {
    const match = /^(\d{2,5})x(\d{2,5})$/.exec(spec);
    if (!match) throw new UsageError(`--viewport must be WIDTHxHEIGHT: ${spec}`);
    return { width: Number(match[1]), height: Number(match[2]) };
  });
}

function schemes(opts) {
  const value = opts.scheme ?? "light";
  if (value === "both") return ["light", "dark"];
  if (value === "light" || value === "dark") return [value];
  throw new UsageError("--scheme must be light, dark or both");
}

// Runs in the page: a short, stable CSS path for reporting.
const SELECTOR_FN = `(el) => {
  const part = (node) => {
    let s = node.tagName.toLowerCase();
    if (node.id) return s + "#" + node.id;
    const cls = [...node.classList].slice(0, 2);
    if (cls.length) s += "." + cls.join(".");
    return s;
  };
  const parts = [];
  for (let node = el; node && node.nodeType === 1 && parts.length < 4; node = node.parentElement) {
    parts.unshift(part(node));
    if (node.id) break;
  }
  return parts.join(" > ");
}`;

async function scrollThrough(page) {
  await page.evaluate(async () => {
    const step = Math.max(200, Math.floor(window.innerHeight * 0.8));
    for (let i = 0; i < 40; i++) {
      const before = window.scrollY;
      window.scrollBy(0, step);
      await new Promise((resolve) => setTimeout(resolve, 120));
      if (window.scrollY === before) break;
    }
    window.scrollTo(0, 0);
  });
  await page.waitForLoadState("networkidle", { timeout: IDLE_TIMEOUT }).catch(() => {});
}

async function measureLayout(page) {
  return page.evaluate(`(() => {
    const sel = ${SELECTOR_FN};
    const root = document.documentElement;
    const vw = root.clientWidth;
    const overflow = { viewport: vw, scrollWidth: root.scrollWidth, offenders: [] };
    if (root.scrollWidth > vw + 1) {
      const hits = new Set();
      for (const el of document.body.querySelectorAll("*")) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && r.right > vw + 1) hits.add(el);
      }
      for (const el of hits) {
        if (hits.has(el.parentElement)) continue;
        const r = el.getBoundingClientRect();
        overflow.offenders.push({ selector: sel(el), right: Math.round(r.right) });
        if (overflow.offenders.length >= 10) break;
      }
    }
    const images = { broken: [], pending: [] };
    for (const img of document.images) {
      const src = img.currentSrc || img.src;
      if (!src) continue;
      if (!img.complete) images.pending.push({ src, selector: sel(img) });
      else if (img.naturalWidth === 0) images.broken.push({ src, selector: sel(img) });
    }
    return { overflow, images };
  })()`);
}

async function runAxe(page, source) {
  await page.addScriptTag({ content: source });
  return page.evaluate(async (tags) => {
    const result = await window.axe.run(document, {
      runOnly: { type: "tag", values: tags },
      resultTypes: ["violations"],
    });
    return result.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      nodes: v.nodes.length,
      targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
    }));
  }, AXE_TAGS);
}

// Tabs through the page and reports focus stops whose computed style does not
// change at all when focused (no outline, ring, border, background or underline).
async function measureFocus(page, steps) {
  await page.evaluate(`(() => {
    const keys = ["outlineStyle", "outlineWidth", "outlineColor", "boxShadow", "borderColor", "backgroundColor", "textDecorationLine", "color"];
    const query = "a[href], button, input, select, textarea, summary, [tabindex], [contenteditable='true']";
    window.__uiCheckKeys = keys;
    window.__uiCheckSeen = new Set();
    window.__uiCheckRest = new Map();
    for (const el of document.querySelectorAll(query)) {
      const cs = getComputedStyle(el);
      window.__uiCheckRest.set(el, keys.map((k) => cs[k]));
    }
    document.activeElement && document.activeElement.blur && document.activeElement.blur();
    window.scrollTo(0, 0);
  })()`);
  const stops = [];
  const missing = [];
  for (let i = 0; i < steps; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(`(() => {
      const sel = ${SELECTOR_FN};
      const el = document.activeElement;
      if (!el || el === document.body || el === document.documentElement) return null;
      if (window.__uiCheckSeen.has(el)) return { wrapped: true };
      window.__uiCheckSeen.add(el);
      const cs = getComputedStyle(el);
      const now = window.__uiCheckKeys.map((k) => cs[k]);
      const rest = window.__uiCheckRest.get(el);
      const ring = cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0;
      const changed = rest ? now.some((v, i) => v !== rest[i]) : null;
      return { selector: sel(el), visible: ring || changed === true, known: !!rest };
    })()`);
    if (!info || info.wrapped) break;
    stops.push(info.selector);
    if (!info.visible && info.known) missing.push(info.selector);
  }
  return { stops: stops.length, missing };
}

async function captureOne(browser, axeSource, opts, target, viewport, scheme, outDir) {
  const contextOptions = {
    viewport,
    colorScheme: scheme,
    deviceScaleFactor: 1,
    bypassCSP: true,
    reducedMotion: "reduce",
  };
  if (viewport.width < 600) Object.assign(contextOptions, { isMobile: true, hasTouch: true });
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  const ignore = opts["ignore-console"] ? new RegExp(opts["ignore-console"]) : null;
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    // Chrome's own "Failed to load resource" line duplicates failedRequests.
    if (text.startsWith("Failed to load resource") || (ignore && ignore.test(text))) return;
    consoleErrors.push(text.slice(0, 300));
  });
  page.on("pageerror", (error) => pageErrors.push(String(error.message || error).slice(0, 300)));
  page.on("requestfailed", (req) => failedRequests.push({ url: req.url(), error: req.failure()?.errorText }));
  page.on("response", (res) => {
    if (res.status() >= 400 && res.request().resourceType() !== "document") {
      failedRequests.push({ url: res.url(), status: res.status() });
    }
  });

  const id = `${target.name}--${viewport.width}x${viewport.height}--${scheme}`;
  const entry = { id, page: target.name, url: target.url, viewport, scheme, failures: [], warnings: [] };
  try {
    const response = await page.goto(target.url, { waitUntil: "load", timeout: NAV_TIMEOUT });
    entry.status = response ? response.status() : null;
    entry.finalUrl = page.url();
    if (entry.status && entry.status >= 400) entry.failures.push(`HTTP ${entry.status}`);
    await page.waitForLoadState("networkidle", { timeout: IDLE_TIMEOUT }).catch(() => {});
    if (opts["wait-for"]) await page.waitForSelector(opts["wait-for"], { timeout: NAV_TIMEOUT });
    await scrollThrough(page);

    const shot = path.join(outDir, "screens", `${id}.png`);
    await page.screenshot({ path: shot, fullPage: true, animations: "disabled", caret: "hide" });
    entry.screenshot = path.relative(outDir, shot);

    const layout = await measureLayout(page);
    entry.overflow = layout.overflow;
    entry.images = layout.images;
    if (layout.overflow.scrollWidth > layout.overflow.viewport + 1) {
      entry.failures.push(`horizontal overflow ${layout.overflow.scrollWidth}px > ${layout.overflow.viewport}px`);
    }
    if (layout.images.broken.length) entry.failures.push(`${layout.images.broken.length} broken image(s)`);
    if (layout.images.pending.length) entry.warnings.push(`${layout.images.pending.length} image(s) still loading`);

    entry.a11y = await runAxe(page, axeSource);
    for (const v of entry.a11y) {
      const line = `axe ${v.id} (${v.impact}) x${v.nodes}`;
      (FAIL_IMPACTS.has(v.impact) ? entry.failures : entry.warnings).push(line);
    }

    entry.focus = await measureFocus(page, opts.focusSteps);
    if (entry.focus.missing.length) entry.failures.push(`${entry.focus.missing.length} focus stop(s) without a visible indicator`);
  } catch (error) {
    entry.failures.push(`check aborted: ${String(error.message || error).split("\n")[0]}`);
  } finally {
    await context.close();
  }
  entry.console = consoleErrors;
  entry.pageErrors = pageErrors;
  entry.failedRequests = failedRequests.slice(0, 20);
  if (pageErrors.length) entry.failures.push(`${pageErrors.length} uncaught page error(s)`);
  if (consoleErrors.length) entry.failures.push(`${consoleErrors.length} console error(s)`);
  if (failedRequests.length) entry.warnings.push(`${failedRequests.length} failed subresource request(s)`);
  return entry;
}

async function capture(opts) {
  if (!opts.out) throw new UsageError("capture needs --out DIR");
  opts.focusSteps = Number(opts["focus-steps"] ?? 25);
  if (!Number.isInteger(opts.focusSteps) || opts.focusSteps < 1 || opts.focusSteps > 500) {
    throw new UsageError("--focus-steps must be an integer from 1 to 500");
  }
  const targets = pages(opts);
  const sizes = viewports(opts);
  const modes = schemes(opts);
  const outDir = path.resolve(opts.out);
  await fs.mkdir(path.join(outDir, "screens"), { recursive: true });
  const axeSource = await fs.readFile(require.resolve("axe-core/axe.min.js"), "utf8");
  const browser = await launch();
  const results = [];
  try {
    for (const target of targets) {
      for (const viewport of sizes) {
        for (const scheme of modes) {
          results.push(await captureOne(browser, axeSource, opts, target, viewport, scheme, outDir));
        }
      }
    }
  } finally {
    await browser.close();
  }
  const failures = results.reduce((n, r) => n + r.failures.length, 0);
  const warnings = results.reduce((n, r) => n + r.warnings.length, 0);
  const report = {
    tool: "web-ui-check",
    version: 1,
    createdAt: new Date().toISOString(),
    verdict: failures ? "fail" : "pass",
    failures,
    warnings,
    results,
  };
  const reportPath = path.join(outDir, "report.json");
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2) + "\n");

  console.log(`web-ui-check: ${report.verdict.toUpperCase()} (${failures} failure(s), ${warnings} warning(s))`);
  console.log(`report: ${reportPath}`);
  for (const r of results) {
    const head = `${r.id}: ${r.failures.length ? "FAIL" : "ok"}`;
    console.log(head + (r.screenshot ? `  [${r.screenshot}]` : ""));
    for (const f of r.failures) console.log(`  - FAIL ${f}`);
    for (const w of r.warnings) console.log(`  - warn ${w}`);
  }
  return failures ? 1 : 0;
}

// --------------------------------------------------------------------------
// compare

async function pngs(dir) {
  // Regular files only: a symlinked PNG could point anywhere.
  const entries = await fs.readdir(dir, { withFileTypes: true });
  return new Set(entries.filter((e) => e.isFile() && e.name.toLowerCase().endsWith(".png")).map((e) => e.name));
}

const COMPOSE_FN = async ({ baseline, current, threshold, label }) => {
  const load = (src) =>
    new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("image failed to decode"));
      img.src = src;
    });
  const [a, b] = await Promise.all([load(baseline), load(current)]);
  const w = Math.max(a.naturalWidth, b.naturalWidth);
  const h = Math.max(a.naturalHeight, b.naturalHeight);
  const pixels = (img) => {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0);
    return ctx.getImageData(0, 0, w, h);
  };
  const pa = pixels(a);
  const pb = pixels(b);
  const diff = document.createElement("canvas");
  diff.width = w;
  diff.height = h;
  const dctx = diff.getContext("2d");
  const out = dctx.createImageData(w, h);
  let changed = 0;
  for (let i = 0; i < pa.data.length; i += 4) {
    const delta = Math.max(
      Math.abs(pa.data[i] - pb.data[i]),
      Math.abs(pa.data[i + 1] - pb.data[i + 1]),
      Math.abs(pa.data[i + 2] - pb.data[i + 2]),
    );
    if (delta > threshold) {
      changed++;
      out.data.set([230, 0, 60, 255], i);
    } else {
      const g = 0.3 * pb.data[i] + 0.59 * pb.data[i + 1] + 0.11 * pb.data[i + 2];
      const faded = 255 - (255 - g) * 0.25;
      out.data.set([faded, faded, faded, 255], i);
    }
  }
  dctx.putImageData(out, 0, 0);
  const ratio = changed / (w * h);
  document.body.innerHTML = "";
  const head = document.createElement("div");
  head.className = "head";
  head.textContent = `${label} — changed pixels ${(ratio * 100).toFixed(2)}%`;
  document.body.append(head);
  const row = document.createElement("div");
  row.className = "row";
  for (const [title, el] of [
    ["baseline", a],
    ["current", b],
    ["diff (red = changed)", diff],
  ]) {
    const col = document.createElement("div");
    col.className = "col";
    const t = document.createElement("div");
    t.className = "title";
    t.textContent = title;
    col.append(t, el);
    row.append(col);
  }
  document.body.append(row);
  return {
    ratio,
    baseline: [a.naturalWidth, a.naturalHeight],
    current: [b.naturalWidth, b.naturalHeight],
  };
};

const COMPOSE_STYLE = `
  body { margin: 0; font: 14px/1.4 -apple-system, sans-serif; background: #fff; color: #111; }
  .head { padding: 8px 12px; font-weight: 600; border-bottom: 1px solid #ccc; }
  .row { display: flex; gap: 8px; padding: 8px; align-items: flex-start; }
  .col { flex: 1; min-width: 0; }
  .title { font-weight: 600; margin-bottom: 4px; }
  .col img, .col canvas { width: 100%; height: auto; display: block; outline: 1px solid #ccc; }
`;

async function compare(opts) {
  for (const key of ["baseline", "current", "out"]) {
    if (!opts[key]) throw new UsageError(`compare needs --${key} DIR`);
  }
  const baseDir = path.resolve(opts.baseline);
  const curDir = path.resolve(opts.current);
  const outDir = path.resolve(opts.out);
  for (const [label, dir] of [["baseline", baseDir], ["current", curDir]]) {
    const stat = await fs.stat(dir).catch(() => null);
    if (!stat?.isDirectory()) {
      throw new Error(`${label} directory does not exist: ${dir}` +
        (label === "baseline" ? " (no approved baseline yet)" : ""));
    }
  }
  const [base, cur] = await Promise.all([pngs(baseDir), pngs(curDir)]);
  await fs.mkdir(outDir, { recursive: true });
  const matched = [...base].filter((n) => cur.has(n)).sort();
  const report = {
    tool: "web-ui-check compare",
    version: 1,
    createdAt: new Date().toISOString(),
    baseline: baseDir,
    current: curDir,
    matched: [],
    onlyBaseline: [...base].filter((n) => !cur.has(n)).sort(),
    onlyCurrent: [...cur].filter((n) => !base.has(n)).sort(),
    failed: [],
  };
  if (matched.length) {
    const browser = await launch();
    try {
      const context = await browser.newContext({ viewport: { width: 1800, height: 200 }, deviceScaleFactor: 1 });
      const page = await context.newPage();
      for (const name of matched) {
        const data = async (dir) =>
          "data:image/png;base64," + (await fs.readFile(path.join(dir, name))).toString("base64");
        try {
          await page.setContent(`<!doctype html><style>${COMPOSE_STYLE}</style><body></body>`);
          const result = await page.evaluate(COMPOSE_FN, {
            baseline: await data(baseDir),
            current: await data(curDir),
            threshold: PIXEL_THRESHOLD,
            label: name,
          });
          const image = path.join(outDir, name);
          await page.screenshot({ path: image, fullPage: true });
          report.matched.push({
            name,
            changedRatio: Number(result.ratio.toFixed(5)),
            size: { baseline: result.baseline, current: result.current },
            image: path.relative(outDir, image),
          });
        } catch (error) {
          // One pair that cannot be composed (e.g. taller than a canvas allows)
          // must not lose the others; it is reported, never counted as unchanged.
          report.failed.push({ name, error: String(error.message || error).split("\n")[0] });
        }
      }
      await context.close();
    } finally {
      await browser.close();
    }
  }
  report.matched.sort((x, y) => y.changedRatio - x.changedRatio);
  const reportPath = path.join(outDir, "compare.json");
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2) + "\n");
  console.log(`web-ui-check compare: ${report.matched.length} matched, report: ${reportPath}`);
  for (const m of report.matched) {
    const sized = m.size.baseline.join("x") === m.size.current.join("x") ? "" : `  size ${m.size.baseline.join("x")} -> ${m.size.current.join("x")}`;
    console.log(`${m.name}: changed ${(m.changedRatio * 100).toFixed(2)}%${sized}  [${m.image}]`);
  }
  for (const f of report.failed) console.log(`${f.name}: NOT COMPARED (${f.error})`);
  for (const n of report.onlyBaseline) console.log(`${n}: missing from current`);
  for (const n of report.onlyCurrent) console.log(`${n}: new (no baseline)`);
  return report.failed.length ? 1 : 0;
}

// --------------------------------------------------------------------------

async function main() {
  const opts = parse(process.argv.slice(2));
  if (opts._ === "capture") return capture(opts);
  if (opts._ === "compare") return compare(opts);
  throw new UsageError(opts._ ? `unknown command: ${opts._}` : "");
}

main().then(
  (code) => process.exit(code),
  (error) => {
    if (error instanceof UsageError) {
      if (error.message) console.error(`web-ui-check: ${error.message}`);
      console.error(USAGE);
    } else {
      console.error(`web-ui-check: ${error.message || error}`);
    }
    process.exit(2);
  },
);
