// Local browser acceptance test for this fixture's lip-sync mouth cues,
// not a generic speech/live-handoff proof. Optional script, not pytest-run.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdtemp } from 'node:fs/promises';
import { resolve, join, extname, sep } from 'node:path';

const CONTENT_TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.txt': 'text/plain', '.wav': 'audio/wav', '.mp4': 'video/mp4' };
const SIZES = { '16:9': [1280, 720], '9:16': [720, 1280] };
const FPS = 30;

const [hfPackage, browserPath, ...roots] = process.argv.slice(2);
assert(hfPackage && browserPath && roots.length,
  'usage: seek.mjs <installed hyperframes/package.json> <headless browser> <fixture roots...>');
const require = createRequire(resolve(hfPackage));
const { default: puppeteer } = await import(require.resolve('puppeteer-core'));

function onlyOne(opacities) {
  const entries = Object.entries(opacities);
  const ones = entries.filter(([, v]) => v === 1);
  const zeros = entries.filter(([, v]) => v === 0);
  assert.equal(ones.length, 1, `expected exactly one mouth opacity=1, got ${JSON.stringify(opacities)}`);
  assert.equal(zeros.length, entries.length - 1, `expected all other mouths opacity=0, got ${JSON.stringify(opacities)}`);
  return ones[0][0].replace('#character-mouth-', '');
}

for (const value of roots) {
  const root = resolve(value);
  const source = join(root, 'project');
  const plan = JSON.parse(await readFile(join(source, 'plan.json'), 'utf8'));
  assert.equal(plan.character.lip_sync, 'cues', `${root}: seek.mjs verifies mouth-cue lip_sync fixtures only`);
  const cues = JSON.parse(await readFile(join(source, plan.character.cues), 'utf8'));
  const mouthNames = Object.keys(plan.character.mouths);
  const mouthIds = mouthNames.map(name => `#character-mouth-${name}`);
  const offset = cues.offset;
  const duration = plan.duration;
  const lastFrame = duration - 1 / FPS;
  const [width, height] = SIZES[plan.aspect];

  const expectedMouth = t => {
    for (const event of cues.events) {
      const start = offset + event.start, end = offset + event.end;
      if (t >= start && t < end) return event.mouth;
    }
    return 'rest';
  };

  const clip = t => Math.min(Math.max(t, 0), lastFrame);
  const times = new Set([0, clip(1), lastFrame]);
  for (const event of cues.events) {
    const start = offset + event.start, end = offset + event.end;
    times.add(clip(start));
    times.add(clip((start + end) / 2));
    times.add(clip(end));
  }
  const orderedTimes = [...times].sort((a, b) => a - b);
  const firstInterior = clip(offset + (cues.events[0].start + cues.events[0].end) / 2);

  const allowed = new Set(['index.html', ...Object.keys(plan.assets)]);
  const server = createServer(async (req, res) => {
    const path = req.url === '/' ? 'index.html' : decodeURIComponent(req.url.slice(1));
    if (!allowed.has(path)) { res.writeHead(404).end(); return; }
    const target = resolve(join(source, path));
    if (target !== resolve(source, path) || !target.startsWith(resolve(source) + sep)) {
      res.writeHead(404).end(); return;
    }
    try {
      const data = await readFile(target);
      res.setHeader('Content-Type', CONTENT_TYPES[extname(path)] || 'application/octet-stream');
      res.end(data);
    } catch { res.writeHead(404).end(); }
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await puppeteer.launch({ executablePath: browserPath, headless: true,
    args: ['--disable-background-networking', '--no-first-run'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width, height });
    await page.setRequestInterception(true);
    page.on('request', req => req.url().startsWith(origin + '/') ? req.continue() : req.abort());
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/');
    await page.evaluate(() => document.fonts.ready);

    const initialOpacities = {};
    for (const id of mouthIds) {
      initialOpacities[id] = await page.$eval(id, el => +getComputedStyle(el).opacity);
    }
    const initialMouth = onlyOne(initialOpacities);
    assert.equal(initialMouth, expectedMouth(0), 'fresh initial mouth state must match cue at time 0 before any seek');

    const readMouths = at => page.evaluate((ids, t) => {
      window.__timelines.explainer.seek(t, false);
      return Object.fromEntries(ids.map(id => [id, +getComputedStyle(document.querySelector(id)).opacity]));
    }, mouthIds, at);

    const expected = {}, forward = {}, reverse = {};
    for (const t of orderedTimes) {
      const forwardOpacities = await readMouths(t);
      const forwardMouth = onlyOne(forwardOpacities);
      await page.evaluate(lf => { window.__timelines.explainer.seek(lf, false); }, lastFrame);
      const reverseOpacities = await readMouths(t);
      const reverseMouth = onlyOne(reverseOpacities);
      const exp = expectedMouth(t);
      assert.equal(forwardMouth, exp, `forward seek mouth mismatch at ${t}`);
      assert.equal(reverseMouth, exp, `reverse seek (after jump to last frame) mouth mismatch at ${t}`);
      expected[t] = exp; forward[t] = forwardOpacities; reverse[t] = reverseOpacities;
    }

    const out = await mkdtemp(join(root, 'seek-proof-'));
    await page.evaluate(t => { window.__timelines.explainer.seek(t, false); }, 0);
    await page.screenshot({ path: join(out, '0.png') });
    await page.evaluate(t => { window.__timelines.explainer.seek(t, false); }, firstInterior);
    await page.screenshot({ path: join(out, `${firstInterior}.png`) });

    assert.equal(errors.length, 0, errors.join('\n'));
    await writeFile(join(out, 'result.json'), JSON.stringify({ root, out, times: orderedTimes,
      expected, forward, reverse, errors,
      proof: 'authored local GSAP seek test, not speech or live handoff' }, null, 2), { flag: 'wx' });
    console.log(JSON.stringify({ root, out, times: orderedTimes.length, status: 'passed' }));
  } finally {
    await browser.close();
    await new Promise(done => server.close(done));
  }
}
