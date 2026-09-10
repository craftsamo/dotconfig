import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile, writeFile, mkdir, realpath} from 'node:fs/promises';
import {readFileSync, realpathSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {dirname, extname, join, resolve, relative, isAbsolute} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const runtime = resolve(here, '../../local/motion-canvas');
const require = createRequire(join(runtime, 'package.json'));
const sha = data => createHash('sha256').update(data).digest('hex');
const json = async path => JSON.parse(await readFile(path, 'utf8'));
const within = (path, root) => { const part = relative(root, path); return part === '' || (!part.startsWith('..') && !isAbsolute(part)); };

function identity() {
  const config = JSON.parse(readFileSync(join(runtime, 'runtime.json'), 'utf8'));
  const lock = sha(readFileSync(join(here, 'package-lock.json')));
  assert.equal(config.lockHash, lock, 'Provisioned lock changed; maintainer setup required');
  assert.equal(sha(readFileSync(join(runtime, 'package-lock.json'))), lock, 'Installed lock differs');
  const [major, minor] = process.versions.node.split('.').map(Number);
  assert(major > 22 || (major === 22 && minor >= 12), 'Node >=22.12 required');
  const browser = spawnSync(config.browser, ['--version'], {encoding: 'utf8', timeout: 15000});
  assert.equal(browser.status, 0, 'Browser unavailable');
  const manifest = JSON.parse(readFileSync(join(here, 'package.json'), 'utf8'));
  for (const [name, version] of Object.entries({...manifest.dependencies, ...manifest.overrides})) {
    const installed = JSON.parse(readFileSync(join(runtime, 'node_modules', name, 'package.json'), 'utf8'));
    assert.equal(installed.version, version, `Dependency version changed: ${name}`);
  }
  const files = ['render.mjs', 'browser.ts', 'contract.ts', 'package.json', 'package-lock.json'];
  return {...config, node: realpathSync(process.execPath), nodeVersion: process.version,
    browserVersion: browser.stdout.trim(),
    adapter: Object.fromEntries(files.map(name => [name, sha(readFileSync(join(here, name)))])),
    platform: process.platform, arch: process.arch};
}

async function run(jobPath) {
  const runtimeIdentity = identity();
  const job = await json(jobPath);
  const project = await realpath(job.project);
  assert.equal(project, job.project, 'Project must use its physical path');
  const out = resolve(job.out);
  assert(!within(out, project), 'Output must be outside frozen project');
  assert.equal(await realpath(dirname(out)), dirname(out), 'Output parent must be physical');
  assert(['snapshot', 'render'].includes(job.mode), 'Invalid operation');
  assert.equal(job.fps, 30);
  assert(Number.isInteger(job.count) && job.count >= 30 && job.count <= 5400, 'Frame count outside bounds');
  assert([[1280, 720], [720, 1280]].some(([w, h]) => w === job.width && h === job.height), 'Invalid canvas');
  assert(Array.isArray(job.samples) && job.samples.length >= 3 && job.samples.length <= 80
    && new Set(job.samples).size === job.samples.length
    && job.samples.every(frame => Number.isInteger(frame) && frame >= 0 && frame < job.count), 'Invalid samples');
  const plan = await json(join(project, 'plan.json'));
  assert.equal(plan.version, 2, 'Motion Canvas requires an approved version 2 project');
  assert.equal(plan.renderer, 'motion-canvas');
  assert.equal(Math.round(plan.duration * job.fps), job.count, 'Job duration differs from plan');
  assert.deepEqual(plan.samples.map(sample => Math.round(sample.at * job.fps)), job.samples, 'Job samples differ from plan');
  assert.deepEqual(plan.aspect === '16:9' ? [1280, 720] : [720, 1280], [job.width, job.height], 'Job canvas differs from plan');
  const meta = await json(join(project, 'scene.meta'));
  assert.equal(meta.version, 1);
  assert(Number.isInteger(meta.seed), 'Frozen scene seed required');
  assert(Array.isArray(meta.timeEvents), 'Frozen time events required');
  const cues = plan.character.cues ? await json(join(project, plan.character.cues)) : null;
  await mkdir(out);
  await mkdir(join(out, 'frames'));
  const buildDir = join(out, 'build');
  await mkdir(buildDir);
  const esbuild = require('esbuild');
  const {default: puppeteer} = await import(require.resolve('puppeteer-core'));
  const virtual = {'@explainer/plan': plan, '@explainer/meta': meta, '@explainer/job': job, '@explainer/cues': cues};
  const built = await esbuild.build({entryPoints: [join(here, 'browser.ts')], outfile: join(buildDir, 'app.js'),
    bundle: true, platform: 'browser', format: 'esm', target: 'chrome120', nodePaths: [join(runtime, 'node_modules')],
    jsx: 'automatic', jsxImportSource: '@motion-canvas/2d/lib', logLevel: 'silent', metafile: true,
    define: {'process.env.NODE_ENV': '"production"'}, loader: {'.glsl': 'text', '.css': 'css', '.woff2': 'file'},
    plugins: [{name: 'frozen-inputs', setup(build) {
      build.onResolve({filter: /^@explainer\//}, args => {
        if (args.path in virtual) return {path: args.path, namespace: 'contract'};
        if (args.path === '@explainer/runtime') return {path: join(here, 'contract.ts')};
        if (args.path === '@explainer/scene') return {path: join(project, 'scene.tsx')};
        throw new Error('Unknown explainer import');
      });
      build.onLoad({filter: /.*/, namespace: 'contract'}, args => ({contents: `export default ${JSON.stringify(virtual[args.path])};`, loader: 'js'}));
      build.onLoad({filter: /.*/, namespace: 'file'}, async args => {
        const path = await realpath(args.path);
        assert(within(path, project) || within(path, join(runtime, 'node_modules'))
          || path === join(here, 'browser.ts') || path === join(here, 'contract.ts'),
          'Import outside frozen source or pinned runtime');
        return null;
      });
      build.onLoad({filter: /\.(png|jpe?g|webp|mp4|svg)$/}, async args => {
        const path = await realpath(args.path);
        assert(within(path, project), 'Media import outside frozen project');
        const name = relative(project, path).replaceAll('\\', '/');
        assert(name in plan.assets, 'Unapproved imported media');
        return {contents: `export default ${JSON.stringify('/' + name)};`, loader: 'js'};
      });
    }}]});
  const files = new Map();
  for (const name of Object.keys(built.metafile.outputs)) {
    const path = resolve(name);
    assert(within(path, buildDir), 'Build output outside staging');
    files.set('/' + relative(buildDir, path).replaceAll('\\', '/'), path);
  }
  for (const name of Object.keys(plan.assets)) files.set('/' + name, join(project, name));
  const html = '<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><link rel="stylesheet" href="/app.css"><script type="module" src="/app.js"></script>';
  const mime = {'.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.wav': 'audio/wav', '.woff2': 'font/woff2'};
  let browser;
  const server = createServer(async (request, response) => {
    const path = new URL(request.url, 'http://127.0.0.1').pathname;
    response.setHeader('Cache-Control', 'no-store');
    if (path === '/') { response.setHeader('Content-Type', 'text/html'); response.end(html); return; }
    if (path === '/app.css' && !files.has(path)) { response.setHeader('Content-Type', 'text/css'); response.end(''); return; }
    if (!files.has(path)) { response.writeHead(404).end(); return; }
    try { response.setHeader('Content-Type', mime[extname(files.get(path))] ?? 'application/octet-stream'); response.end(await readFile(files.get(path))); }
    catch { response.writeHead(404).end(); }
  });
  const abort = new AbortController();
  const stop = () => abort.abort();
  process.once('SIGTERM', stop); process.once('SIGINT', stop);
  let timeout;
  try {
    await new Promise(done => server.listen(0, '127.0.0.1', done));
    const origin = `http://127.0.0.1:${server.address().port}`;
    browser = await puppeteer.launch({executablePath: runtimeIdentity.browser, headless: true,
      args: ['--disable-background-networking', '--no-first-run', '--mute-audio', '--disable-extensions']});
    await writeFile(join(out, 'worker.json'), JSON.stringify({nodePid: process.pid,
      browserPid: browser.process().pid, port: server.address().port}) + '\n', {flag: 'wx'});
    const page = await browser.newPage();
    await page.setViewport({width: job.width, height: job.height, deviceScaleFactor: 1});
    await page.setRequestInterception(true);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.origin === origin || url.protocol === 'data:' || url.protocol === 'blob:') request.continue();
      else { errors.push('External request blocked'); request.abort(); }
    });
    const audits = [], frames = {}, wanted = new Set(job.samples);
    let next = 0, bytes = 0;
    await page.exposeFunction('pipelineFrame', async (frame, data, audit) => {
      assert(!abort.signal.aborted, 'Render cancelled');
      assert.equal(frame, next++, 'Nonsequential or duplicate frame');
      assert(frame < job.count, 'Too many frames');
      if (wanted.has(frame)) audits.push(audit);
      if (job.mode === 'snapshot' && !wanted.has(frame)) { assert.equal(data, null); return; }
      assert(typeof data === 'string' && data.startsWith('data:image/png;base64,'), 'PNG frame required');
      const buffer = Buffer.from(data.slice(22), 'base64');
      assert(buffer.length < 8_000_000 && buffer.readUInt32BE(16) === job.width && buffer.readUInt32BE(20) === job.height, 'PNG dimensions/size mismatch');
      bytes += buffer.length;
      assert(bytes <= 2_000_000_000, 'Frame output exceeds 2 GB');
      const name = `${String(frame).padStart(6, '0')}.png`;
      await writeFile(join(out, 'frames', name), buffer, {flag: 'wx'});
      frames[name] = sha(buffer);
    });
    await page.goto(origin + '/', {waitUntil: 'networkidle0', timeout: 60000});
    await page.waitForFunction('typeof window.startRender === "function"', {timeout: 60000});
    await page.evaluate(async () => {
      await Promise.all([...document.fonts].map(face => face.load()));
      await document.fonts.ready;
    });
    if (abort.signal.aborted) throw new Error('Render cancelled');
    const cancelled = new Promise((_, reject) => {
      abort.signal.addEventListener('abort', () => reject(new Error('Render cancelled')), {once: true});
      timeout = setTimeout(() => reject(new Error('Render exceeded 10 minutes')), 600000);
    });
    const result = await Promise.race([page.evaluate(() => window.startRender()), cancelled]);
    assert(result.ok && errors.length === 0, JSON.stringify(errors));
    assert.equal(next, job.count, 'Scene is shorter than approved duration');
    assert.equal(Object.keys(frames).length, job.mode === 'render' ? job.count : wanted.size, 'Missing frames');
    assert.equal(audits.length, wanted.size, 'Missing sample audits');
    const report = {ok: true, frames, audits, runtime: runtimeIdentity, count: next, bytes,
      contrast: 'manual review required', evidence: 'Motion Canvas frames; not listening or semantic approval'};
    await writeFile(join(out, 'audit.json'), JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
    return report;
  } finally {
    clearTimeout(timeout);
    if (browser) await browser.close();
    server.closeAllConnections();
    await new Promise(done => server.close(done));
    process.removeListener('SIGTERM', stop); process.removeListener('SIGINT', stop);
  }
}

try {
  if (process.argv[2] === '--identity' && process.argv.length === 3) console.log(JSON.stringify(identity()));
  else {
    assert(process.argv[2] === '--job' && process.argv.length === 4, 'usage: render.mjs --identity | --job <job.json>');
    const result = await run(process.argv[3]);
    console.log(JSON.stringify({ok: result.ok, count: result.count, bytes: result.bytes}));
  }
} catch (error) {
  console.error(JSON.stringify({ok: false, error: error.message}));
  process.exitCode = 1;
}
