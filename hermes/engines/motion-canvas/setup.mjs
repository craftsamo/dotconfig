// Explicit maintainer provisioning; rendering never runs this script.
import {copyFileSync, existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const runtime = resolve(here, '../../local/motion-canvas');
const argv = process.argv.slice(2);
if (argv.length !== 2 || argv[0] !== '--browser') {
  throw new Error('usage: node setup.mjs --browser <installed Chromium executable>');
}
const sourceBrowser = realpathSync(argv[1]);
const version = spawnSync(sourceBrowser, ['--version'], {encoding: 'utf8', timeout: 15000});
if (version.status !== 0) throw new Error('Cannot query the supplied browser');
const marker = resolve(runtime, 'runtime.json');
const previous = existsSync(marker) ? JSON.parse(readFileSync(marker, 'utf8')) : null;
const lockHash = createHash('sha256').update(readFileSync(resolve(here, 'package-lock.json'))).digest('hex');
if (previous && previous.lockHash !== lockHash) {
  throw new Error('Pinned dependencies changed; preserve the old runtime and provision a fresh one explicitly');
}
mkdirSync(runtime, {recursive: true});
for (const file of ['package.json', 'package-lock.json']) {
  const src = resolve(here, file), dest = resolve(runtime, file);
  if (existsSync(dest)) {
    if (!readFileSync(src).equals(readFileSync(dest))) throw new Error(`Refusing to overwrite ${file}`);
  } else {
    copyFileSync(src, dest);
  }
}
if (!previous) {
  const install = spawnSync('npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund'], {
    cwd: runtime, stdio: 'inherit', timeout: 600_000,
  });
  if (install.status !== 0) throw new Error('Pinned runtime installation failed');
}
let browser = sourceBrowser;
if (process.platform === 'darwin' && sourceBrowser.includes('.app/Contents/MacOS/')) {
  // A separate app path avoids macOS activating a headless everyday browser
  // when the owner opens its Dock icon. Never edit the signed app's contents.
  const split = sourceBrowser.indexOf('.app/') + 4;
  const app = sourceBrowser.slice(0, split);
  const destination = resolve(runtime, 'browser/Renderer.app');
  mkdirSync(dirname(destination), {recursive: true});
  if (!existsSync(destination)) {
    const copied = spawnSync('cp', ['-Rc', app, destination], {encoding: 'utf8', timeout: 120000});
    if (copied.status !== 0) throw new Error('Dedicated APFS browser clone failed');
  }
  browser = destination + sourceBrowser.slice(split);
  const cloned = spawnSync(browser, ['--version'], {encoding: 'utf8', timeout: 15000});
  if (cloned.status !== 0 || cloned.stdout.trim() !== version.stdout.trim()) {
    throw new Error(`Dedicated browser clone differs at ${destination}; preserve old previews and provision a fresh clone explicitly`);
  }
}
writeFileSync(marker, JSON.stringify({
  version: 1, browser, browserVersion: version.stdout.trim(),
  node: realpathSync(process.execPath), nodeVersion: process.version, lockHash,
}, null, 2) + '\n', {flag: previous ? 'w' : 'wx'});
console.log(JSON.stringify({runtime, browserVersion: version.stdout.trim(), provisioned: true}));
