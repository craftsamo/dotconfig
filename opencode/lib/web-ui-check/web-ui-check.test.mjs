// node --test opencode/lib/web-ui-check/web-ui-check.test.mjs
// Runs the real CLI against local pages; needs Playwright's headless shell.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

const CLI = path.join(path.dirname(fileURLToPath(import.meta.url)), "web-ui-check.mjs");
const PAGES = {
  "/good.html": `<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">
    <title>good</title></head><body><main><h1>Good</h1><a href="#x">link</a><button>go</button></main></body></html>`,
  "/bad.html": `<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">
    <title>bad</title><style>a:focus{outline:none}.wide{width:900px}</style></head>
    <body><main><h1>Bad</h1><div class="wide">wide</div><img src="missing.png" alt="gone">
    <a href="#x">one</a><a href="#y">two</a><script>console.error("boom")</script></main></body></html>`,
};

let server;
let base;
let tmp;

before(async () => {
  tmp = await fs.mkdtemp(path.join(os.tmpdir(), "web-ui-check-test-"));
  server = http.createServer((req, res) => {
    const body = PAGES[req.url];
    res.writeHead(body ? 200 : 404, { "content-type": "text/html" });
    res.end(body ?? "not found");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  server.close();
  await fs.rm(tmp, { recursive: true, force: true });
});

// Asynchronous on purpose: the test server answers from this same event loop.
function cli(...args) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [CLI, ...args]);
    let out = "";
    child.stdout.on("data", (chunk) => { out += chunk; });
    child.stderr.on("data", (chunk) => { out += chunk; });
    child.on("close", (code) => resolve({ code, out }));
  });
}

test("a clean page passes and is photographed per viewport", async () => {
  const out = path.join(tmp, "good");
  const run = await cli("capture", "--out", out, "--page", `home=${base}/good.html`, "--viewport", "800x600");
  assert.equal(run.code, 0, run.out);
  const report = JSON.parse(await fs.readFile(path.join(out, "report.json"), "utf8"));
  assert.equal(report.verdict, "pass");
  await fs.access(path.join(out, "screens", "home--800x600--light.png"));
});

test("measurable defects fail with exit 1", async () => {
  const out = path.join(tmp, "bad");
  const run = await cli("capture", "--out", out, "--page", `bad=${base}/bad.html`, "--viewport", "375x812");
  assert.equal(run.code, 1, run.out);
  const [entry] = JSON.parse(await fs.readFile(path.join(out, "report.json"), "utf8")).results;
  const text = entry.failures.join("\n");
  for (const expected of ["horizontal overflow", "broken image", "console error", "without a visible indicator"]) {
    assert.match(text, new RegExp(expected), text);
  }
  assert.equal(entry.focus.missing.length, 2, "two links with the same path are two stops, not a wrap");
});

test("compare pairs by name and reports the unmatched", async () => {
  const baseline = path.join(tmp, "baseline");
  await fs.mkdir(baseline);
  await fs.copyFile(path.join(tmp, "good", "screens", "home--800x600--light.png"),
    path.join(baseline, "home--800x600--light.png"));
  await fs.copyFile(path.join(tmp, "good", "screens", "home--800x600--light.png"),
    path.join(baseline, "gone--800x600--light.png"));
  const out = path.join(tmp, "cmp");
  const run = await cli("compare", "--baseline", baseline, "--current", path.join(tmp, "good", "screens"), "--out", out);
  assert.equal(run.code, 0, run.out);
  const report = JSON.parse(await fs.readFile(path.join(out, "compare.json"), "utf8"));
  assert.deepEqual(report.matched.map((m) => [m.name, m.changedRatio]), [["home--800x600--light.png", 0]]);
  assert.deepEqual(report.onlyBaseline, ["gone--800x600--light.png"]);
  await fs.access(path.join(out, "home--800x600--light.png"));
});

test("usage errors and a missing baseline exit 2", async () => {
  assert.equal((await cli("capture", "--out", tmp)).code, 2);
  assert.equal((await cli("capture", "--out", tmp, "--page", "x=ftp://nope")).code, 2);
  assert.equal((await cli("capture", "--out", tmp, "--page", `x=${base}/good.html`, "--focus-steps", "zero")).code, 2);
  const missing = await cli("compare", "--baseline", path.join(tmp, "nope"), "--current", tmp, "--out", tmp);
  assert.equal(missing.code, 2);
  assert.match(missing.out, /no approved baseline yet/);
});
