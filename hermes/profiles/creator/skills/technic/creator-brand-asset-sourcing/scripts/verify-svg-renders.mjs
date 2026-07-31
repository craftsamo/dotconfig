// Verify SVG logos actually rasterize to visible ink.
//
//   npm i puppeteer-core
//   node verify-svg-renders.mjs logo-a.svg logo-b.svg
//   node verify-svg-renders.mjs            # defaults to *.svg in cwd
//
// Why this exists: a structurally valid SVG can render completely blank
// (bad viewBox, white-on-white, zero-size paths). xmllint will not catch it.
//
// Two traps this deliberately avoids:
//   1. PNG byte-length is NOT a blank detector. Use real pixel counting.
//   2. Forcing a wide mark into a square box produces false failures.
//      Aspect ratio is preserved below.
// Ink is measured against a MID-GREY backdrop so white-ink and black-ink
// variants both register.

import puppeteer from 'puppeteer-core';
import { readFileSync, readdirSync } from 'fs';

const CHROME =
  process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BOX = 256;      // fit box; aspect ratio preserved
const MIN_INK = 1.0;  // % of bounding box that must differ from backdrop

const files = process.argv.slice(2).length
  ? process.argv.slice(2)
  : readdirSync('.').filter(f => f.endsWith('.svg'));

if (!files.length) {
  console.error('no .svg files given or found');
  process.exit(1);
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox'],
});
const page = await browser.newPage();

let fail = 0;
for (const f of files) {
  const svg = readFileSync(f, 'utf8');
  let r;
  try {
    r = await page.evaluate(
      async (svg, BOX) => {
        const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
        const img = new Image();
        await new Promise((ok, no) => ((img.onload = ok), (img.onerror = no), (img.src = url)));
        const k = BOX / Math.max(img.width, img.height); // preserve aspect
        const w = Math.round(img.width * k);
        const h = Math.round(img.height * k);
        const c = Object.assign(document.createElement('canvas'), { width: w, height: h });
        const ctx = c.getContext('2d');
        ctx.fillStyle = '#808080'; // reveals both white and black ink
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        const d = ctx.getImageData(0, 0, w, h).data;
        let ink = 0;
        for (let i = 0; i < d.length; i += 4) {
          if (
            Math.abs(d[i] - 128) > 24 ||
            Math.abs(d[i + 1] - 128) > 24 ||
            Math.abs(d[i + 2] - 128) > 24
          ) ink++;
        }
        return { ink, total: w * h, w, h };
      },
      svg,
      BOX
    );
  } catch (e) {
    console.log(`FAIL  ${f.padEnd(30)} did not load: ${e.message}`);
    fail++;
    continue;
  }

  const pct = (r.ink / r.total) * 100;
  const ok = pct > MIN_INK;
  if (!ok) fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${f.padEnd(30)} ${r.w}x${r.h}  ink=${pct.toFixed(1)}%`);
}

await browser.close();
console.log(fail ? `${fail} FAILED` : 'ALL RENDER NON-BLANK');
process.exit(fail ? 1 : 0);
