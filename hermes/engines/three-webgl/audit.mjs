// Independent layer audit: raw source, same pinned browser/software backend.
// This does not replace HyperFrames checks or inspection of the encoded movie.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFileSync, realpathSync, statSync, writeFileSync} from 'node:fs';
import {dirname, extname, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const runtime = resolve(here, '../../local/three-webgl');
const [projectArg, timesArg, output] = process.argv.slice(2);
const project = realpathSync(projectArg);
const times = JSON.parse(timesArg);
assert(Array.isArray(times) && times.length > 0 && times.length <= 80 && times.every(Number.isFinite));
const marker = JSON.parse(readFileSync(resolve(runtime, 'runtime.json')));
const require = createRequire(resolve(runtime, 'package.json'));
const puppeteer = require('puppeteer-core');
const errors = [];
let browser, browserExited;
const server = createServer((req, res) => {
  try {
    assert(req.method === 'GET' || req.method === 'HEAD');
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    const path = realpathSync(resolve(project, '.' + (pathname === '/' ? '/index.html' : pathname)));
    assert(path.startsWith(project + sep) && statSync(path).isFile());
    const type = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png',
                  '.jpg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2'}[extname(path)] || 'application/octet-stream';
    res.writeHead(200, {'Content-Type': type});
    res.end(req.method === 'HEAD' ? undefined : readFileSync(path));
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const origin = `http://127.0.0.1:${server.address().port}`;
const abort = new AbortController();
const stop = () => {
  abort.abort();
  const pid = browser?.process()?.pid;
  if (pid) {
    // Puppeteer owns a detached browser group; killing only Node can orphan it.
    try { process.kill(process.platform === 'win32' ? pid : -pid, 'SIGKILL'); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
  }
  server.closeAllConnections();
};
process.once('SIGTERM', stop); process.once('SIGINT', stop);
try {
  browser = await puppeteer.launch({executablePath: marker.browser, headless: true,
    signal: abort.signal, handleSIGTERM: false, handleSIGINT: false,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-background-networking',
           '--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  const child = browser.process();
  browserExited = child.exitCode !== null || child.signalCode !== null ? Promise.resolve() :
    new Promise(done => child.once('exit', done));
  writeFileSync(resolve(dirname(output), 'graphics-worker.json'), JSON.stringify({nodePid: process.pid,
    browserPid: browser.process().pid, port: server.address().port}) + '\n', {flag: 'wx'});
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.setRequestInterception(true);
  page.on('request', request => {
    if (new URL(request.url()).origin === origin) request.continue();
    else { errors.push('Nonlocal request blocked'); request.abort(); }
  });
  await page.goto(origin, {waitUntil: 'networkidle0', timeout: 30000});
  await page.evaluate(() => document.fonts.ready);
  const ready = await page.evaluate(() => ({audit: window.__hermesThreeAudit,
    hook: typeof window.__hfThreeRender, canvases: document.querySelectorAll('canvas').length}));
  assert.equal(ready.hook, 'function', 'Three render hook was not registered');
  assert.equal(ready.canvases, 1, 'One audited canvas required');
  assert.match(ready.audit.renderer, /swiftshader/i, 'Actual WebGL backend must be SwiftShader');
  const frames = {};
  // Revisit every time after reverse seeking; equality is byte-exact on this pinned runtime.
  for (const time of [...times, ...times.toReversed(), ...times]) {
    assert(!abort.signal.aborted, 'Graphics audit cancelled');
    const frame = await page.evaluate(t => {
      window.__hfThreeTime = t;
      window.__hfThreeRender();
      return {audit: window.__hermesThreeAudit, png: document.querySelector('canvas').toDataURL('image/png')};
    }, time);
    assert.deepEqual(frame.audit.errors, [], 'Three layer retained errors');
    assert.equal(frame.audit.time, time, 'Three clock differs from requested seek');
    assert(frame.audit.calls > 0 && frame.audit.programs > 0, 'No actual WebGL draw/program');
    const hash = createHash('sha256').update(Buffer.from(frame.png.split(',')[1], 'base64')).digest('hex');
    if (frames[String(time)]) assert.equal(frames[String(time)], hash, 'Layer changed after reverse seek');
    frames[String(time)] = hash;
  }
  assert.deepEqual(errors, [], 'Browser errors or nonlocal requests');
  writeFileSync(output, JSON.stringify({version: 1, status: 'PASS', renderer: ready.audit.renderer,
    width: ready.audit.width, height: ready.audit.height, frames, reverseSeek: 'byte-identical',
    scope: 'WebGL layer only; encoded movie and DOM appearance need separate review'}, null, 2) + '\n', {flag: 'wx'});
} finally {
  try {
    if (browser) await browser.close();
    // Wait for the owned child's actual exit, not only protocol disconnection.
    if (browserExited) await browserExited;
  }
  finally {
    server.closeAllConnections();
    await new Promise(done => server.close(done));
    process.removeListener('SIGTERM', stop); process.removeListener('SIGINT', stop);
  }
}
