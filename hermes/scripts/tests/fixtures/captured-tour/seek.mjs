// Fixture-only acceptance proof using the installed HyperFrames runtime.
// This never assigns video.currentTime: the framework must own media seeking.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {dirname, extname, join, resolve} from 'node:path';

const [hfPackage, executablePath, projectValue, outValue] = process.argv.slice(2);
assert(hfPackage && executablePath && projectValue && outValue, 'usage: seek.mjs <hf package.json> <browser> <project> <fresh output>');
const require = createRequire(resolve(hfPackage));
const {default: puppeteer} = await import(require.resolve('puppeteer-core'));
const sharp = require('sharp');
const project = resolve(projectValue), out = resolve(outValue);
await mkdir(out);
const runtime = await readFile(join(dirname(hfPackage), 'dist/hyperframe-runtime.js'));
const server = createServer(async (req, res) => {
  try {
    if (req.url === '/runtime.js') { res.setHeader('Content-Type', 'text/javascript'); res.end(runtime); return; }
    const path = req.url === '/' ? 'index.html' : req.url.slice(1);
    assert(/^(index\.html|assets\/[a-zA-Z0-9_./-]+)$/.test(path) && !path.includes('..'));
    let data = await readFile(join(project, path));
    if (path === 'index.html') data = data.toString().replace('<head>', '<head><script src="/runtime.js"></script>');
    res.setHeader('Content-Type', ({'.js':'text/javascript','.mp4':'video/mp4','.html':'text/html'})[extname(path)] || 'application/octet-stream');
    if (extname(path) === '.mp4') {
      res.setHeader('Accept-Ranges','bytes');
      const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');
      if (range) {
        const start=Number(range[1]), end=range[2] ? Number(range[2]) : data.length-1;
        assert(start<=end && end<data.length);
        res.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${data.length}`,'Content-Length':end-start+1});
        res.end(data.subarray(start,end+1));return;
      }
    }
    res.setHeader('Content-Length',Buffer.byteLength(data));
    res.end(data);
  } catch { res.writeHead(404).end(); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await puppeteer.launch({executablePath, headless:true, args:['--disable-background-networking','--no-first-run']});
try {
  const page = await browser.newPage();
  await page.setViewport({width:1280,height:720});
  await page.setRequestInterception(true);
  page.on('request', req => req.url().startsWith(origin+'/') ? req.continue() : req.abort());
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'warning') console.log(message.text()); });
  await page.goto(origin+'/');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => document.querySelector('video').readyState >= 2);
  await page.waitForFunction(() => window.__playerReady && window.__renderReady);
  const mapping = JSON.parse(await readFile(join(project,'assets/footage/media.json'),'utf8')).clips[0];
  const records = [];
  const times = [3,5,7,10,12].filter(t => t < mapping.timeline_start + mapping.duration);
  const seek = async at => {
    await page.evaluate(async time => {
      await window.__player.renderSeek(time);
      await window.__hfWaitForSeekCompletion();
    }, at);
    await page.waitForFunction(() => {const video=document.querySelector('video');return !video.seeking && video.readyState>=2;});
    await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
    return await page.$eval('video', el => ({currentTime:el.currentTime,seeking:el.seeking,readyState:el.readyState}));
  };
  for (const time of times) {
    const state = await seek(time);
    assert(Math.abs(state.currentTime-(time-mapping.timeline_start)) < 1/30, JSON.stringify({time,state}));
    const forward = await page.screenshot({path:join(out,`${time}-forward.png`)});
    await seek(19);
    const reversed = await seek(time);
    const reverse = await page.screenshot({path:join(out,`${time}-reverse.png`)});
    const a = await sharp(forward).removeAlpha().raw().toBuffer();
    const b = await sharp(reverse).removeAlpha().raw().toBuffer();
    let changed = 0, maxDelta = 0;
    for (let i=0;i<a.length;i++) {const delta=Math.abs(a[i]-b[i]);if(delta)changed++;maxDelta=Math.max(maxDelta,delta);}
    assert(maxDelta<=1 && changed<=48, `reverse seek differs at ${time}: ${changed}/${maxDelta}`);
    const hash = value => createHash('sha256').update(value).digest('hex');
    records.push({time,sourceTime:time-mapping.timeline_start+mapping.source_start,state,reversed,
      forward:hash(forward),reverse:hash(reverse),changed,maxDelta});
  }
  assert(new Set(records.map(r=>r.forward)).size >= 3, 'moving footage must contain distinct UI states');
  await writeFile(join(out,'seek.json'),JSON.stringify({records,errors,frameworkOwned:true},null,2),{flag:'wx'});
  assert.equal(errors.length, 0, errors.join('\n'));
  console.log(JSON.stringify({out, samples:records.length, status:'passed', frameworkOwned:true}));
} finally {
  await browser.close();
  await new Promise(done => server.close(done));
}
