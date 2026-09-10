// Local browser acceptance test for this fixture, not a generic runtime engine.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdtemp } from 'node:fs/promises';
import { resolve, join, extname } from 'node:path';

const [hfPackage, browserPath, ...roots] = process.argv.slice(2);
assert(hfPackage && browserPath && roots.length, 'usage: seek.mjs <installed hyperframes/package.json> <headless browser> <fixture roots...>');
const require = createRequire(resolve(hfPackage));
const { default: puppeteer } = await import(require.resolve('puppeteer-core'));
const sharp = require('sharp');
for (const value of roots) {
  const root = resolve(value);
  const source = join(root, 'project');
  const out = await mkdtemp(join(root, 'seek-proof-'));
  const server = createServer(async (req, res) => {
    const path = req.url === '/' ? 'index.html' : req.url.slice(1);
    if (!/^(index\.html|assets\/[a-zA-Z0-9_.-]+)$/.test(path)) {
      res.writeHead(404).end(); return;
    }
    try {
      const data = await readFile(join(source, path));
      res.setHeader('Content-Type', extname(path) === '.js' ? 'text/javascript' : 'text/html');
      res.end(data);
    } catch { res.writeHead(404).end(); }
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await puppeteer.launch({ executablePath: browserPath, headless: true,
    args: ['--disable-background-networking', '--no-first-run'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720 });
    await page.setRequestInterception(true);
    page.on('request', req => req.url().startsWith(origin + '/') ? req.continue() : req.abort());
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/');
    await page.evaluate(() => document.fonts.ready);
    const total = await page.$eval('#root', el => +el.dataset.duration);
    const form = JSON.parse(await readFile(join(source, 'form.json'), 'utf8'));
    const k = total / 20;
    const results = {};
    for (const t of [0, 2.7, 6, 6.6, 9, 9.6, 10.8, 10.95, 12.4, 14.1, 15.5, 18.7]) {
      results[t] = await page.evaluate(at => {
        window.__timelines.tour.seek(at, false);
        const css = id => getComputedStyle(document.querySelector(id));
        const rect = id => {
          const r = document.querySelector(id).getBoundingClientRect();
          return { x: r.x, y: r.y, right: r.right, bottom: r.bottom };
        };
        return { background: css('#app').backgroundColor, modal: +css('#modal').opacity,
          saved: +css('#saved-name').opacity, completion: +css('#completion').opacity,
          typed: [...document.querySelectorAll('#field span')].filter(el => +getComputedStyle(el).opacity > .5).length,
          window: rect('#window'), pointer: rect('#cursor'), dark: rect('#dark-choice'),
          customize: rect('#customize'), field: rect('#field'), save: rect('#save') };
      }, t*k);
    }
    assert.notEqual(results[2.7].background, results[6.6].background);
    assert.equal(results[6.6].modal, 0);
    assert.equal(results[9.6].modal, 1);
    assert(results[10.95].typed > 0 && results[10.95].typed < 4);
    assert.equal(results[12.4].typed, 4);
    assert.equal(results[15.5].modal, 0);
    assert.equal(results[15.5].saved, 1);
    if (form.intro === 'result-first') assert.equal(results[0].background, results[6.6].background, 'result-first must already be Dark at frame zero');
    if (form.outro === 'none') assert.equal(results[18.7].completion, 0, 'none must not add completion beat');
    for (const [time, target] of [[6, 'dark'], [9, 'customize'], [10.8, 'field'], [14.1, 'save']]) {
      const state = results[time], p = state.pointer, box = state[target];
      assert(p.x >= box.x && p.x <= box.right && p.y >= box.y && p.y <= box.bottom, `pointer misses ${target}`);
    }
    const hashes = {};
    for (const time of [2.7, 6.6, 10.95, 12.4, 18.7]) {
      await page.evaluate(t => { window.__timelines.tour.seek(t, false); }, time*k);
      // The timeline is paused; wait for the compositor, not animation time.
      await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
      const first = await page.screenshot({ path: join(out, `${time}.png`) });
      await page.evaluate(t => { window.__timelines.tour.seek(t, false); }, total - 1/30);
      await page.evaluate(t => { window.__timelines.tour.seek(t, false); }, time*k);
      await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
      const reversed = await page.screenshot({ path: join(out, `${time}-reverse.png`) });
      const hash = b => createHash('sha256').update(b).digest('hex');
      const a = await sharp(first).removeAlpha().raw().toBuffer();
      const b = await sharp(reversed).removeAlpha().raw().toBuffer();
      let changedChannels = 0, maxChannelDelta = 0;
      for (let i=0; i<a.length; i++) {
        const delta = Math.abs(a[i]-b[i]);
        if (delta) changedChannels++;
        maxChannelDelta = Math.max(maxChannelDelta, delta);
      }
      // Observed Chrome raster noise: four pixels differing by one 8-bit unit.
      // Permit only <=16 RGB pixels at that precision, not geometry/text drift.
      assert(maxChannelDelta <= 1 && changedChannels <= 48, `reverse seek differs at ${time}`);
      hashes[time] = { forward: hash(first), reverse: hash(reversed), changedChannels, maxChannelDelta };
    }
    assert.equal(errors.length, 0, errors.join('\n'));
    await writeFile(join(out, 'result.json'), JSON.stringify({ results, reverseSeekHashes: hashes,
      assertions: 17 + Number(form.intro === 'result-first') + Number(form.outro === 'none'), runtimeErrors: errors,
      evidence: 'local headless fixture; no live OS/model handoff' }, null, 2), { flag: 'wx' });
    console.log(JSON.stringify({ root, out, reverseSeekFrames: 5, status: 'passed' }));
  } finally {
    await browser.close();
    await new Promise(done => server.close(done));
  }
}
