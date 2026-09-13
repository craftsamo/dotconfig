// Maintainer-only provisioning. Jobs stage installed assets; they never install.
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {copyFileSync, existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const runtime = resolve(here, '../../local/three-webgl');
const args = process.argv.slice(2);
const refresh = args.includes('--refresh');
if (refresh) args.splice(args.indexOf('--refresh'), 1);
if (args.length !== 2 || args[0] !== '--browser') {
  throw new Error('usage: node setup.mjs --browser <dedicated Chromium> [--refresh]');
}
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const run = (exe, argv, options = {}) => {
  const result = spawnSync(exe, argv, {encoding: 'utf8', timeout: 30000, ...options});
  if (result.status !== 0) throw new Error(`${exe} failed: ${result.stderr || result.error || result.status}`);
  return (result.stdout || '').trim();
};
const sourceBrowser = realpathSync(args[1]);
const hyperframes = resolve(runtime, 'node_modules/hyperframes/bin/hyperframes.mjs');
const browserVersion = run(sourceBrowser, ['--version']);
const cliHashes = () => Object.fromEntries(['cli.js', 'hyperframe.runtime.iife.js'].map(name => [name, sha(resolve(dirname(hyperframes), '../dist', name))]));
const inputs = Object.fromEntries(['package.json', 'package-lock.json', 'setup.mjs', 'three-layer.js', 'audit.mjs'].map(name => [name, sha(resolve(here, name))]));
const marker = resolve(runtime, 'runtime.json');
const previous = existsSync(marker) ? JSON.parse(readFileSync(marker)) : null;
if (previous && previous.inputs['package-lock.json'] !== inputs['package-lock.json']) {
  throw new Error('Dependency pin changed; preserve this runtime and provision its replacement explicitly');
}
if (previous && !refresh) {
  if (JSON.stringify(previous.inputs) !== JSON.stringify(inputs)) throw new Error('Engine source drift; explicit --refresh required');
  for (const [name, hash] of Object.entries(previous.assets)) {
    if (sha(resolve(runtime, 'assets', name)) !== hash) throw new Error(`Runtime asset drift: ${name}`);
  }
  if (run(process.execPath, [hyperframes, '--version']) !== '0.8.35' ||
      JSON.stringify(previous.hyperframesHashes) !== JSON.stringify(cliHashes()) ||
      previous.browserVersion !== browserVersion || previous.browserHash !== sha(sourceBrowser) ||
      previous.hyperframes !== hyperframes || previous.node !== realpathSync(process.execPath)) {
    throw new Error('Browser/CLI/Node identity changed; explicit reprovisioning and new preview required');
  }
  console.log(JSON.stringify({provisioned: true, reused: true, runtime}));
  process.exit(0);
}
mkdirSync(runtime, {recursive: true});
for (const name of ['package.json', 'package-lock.json']) {
  const src = resolve(here, name), dest = resolve(runtime, name);
  if (existsSync(dest) && !readFileSync(src).equals(readFileSync(dest))) throw new Error(`Refusing to overwrite ${name}`);
  if (!existsSync(dest)) copyFileSync(src, dest);
}
if (!previous) run('npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund'], {cwd: runtime, stdio: 'inherit', timeout: 600000});
const cliVersion = run(process.execPath, [hyperframes, '--version']);
if (cliVersion !== '0.8.35') throw new Error('Pinned HyperFrames version mismatch');
const hyperframesHashes = cliHashes();
let browser = sourceBrowser;
if (process.platform === 'darwin' && sourceBrowser.includes('.app/Contents/MacOS/')) {
  const split = sourceBrowser.indexOf('.app/') + 4;
  const destination = resolve(runtime, 'browser/Renderer.app');
  mkdirSync(dirname(destination), {recursive: true});
  if (!existsSync(destination)) run('cp', ['-Rc', sourceBrowser.slice(0, split), destination], {timeout: 120000});
  browser = destination + sourceBrowser.slice(split);
  if (run(browser, ['--version']) !== browserVersion || sha(browser) !== sha(sourceBrowser)) throw new Error('Dedicated clone differs');
} else if (sourceBrowser.endsWith('/chrome-headless-shell')) {
  const destination = resolve(runtime, 'browser/headless-shell');
  mkdirSync(dirname(destination), {recursive: true});
  if (!existsSync(destination)) run('cp', [process.platform === 'darwin' ? '-Rc' : '-R', dirname(sourceBrowser), destination], {timeout: 120000});
  browser = resolve(destination, 'chrome-headless-shell');
  if (run(browser, ['--version']) !== browserVersion || sha(browser) !== sha(sourceBrowser)) throw new Error('Dedicated headless browser differs');
}
const require = createRequire(resolve(runtime, 'package.json'));
const esbuild = require('esbuild');
const assets = resolve(runtime, 'assets');
mkdirSync(assets, {recursive: true});
await esbuild.build({stdin: {contents: 'export * from "three";', resolveDir: runtime},
  bundle: true, format: 'iife', globalName: 'THREE', platform: 'browser', target: 'es2022',
  minify: true, legalComments: 'inline', outfile: resolve(assets, 'three-runtime.js')});
copyFileSync(resolve(here, 'three-layer.js'), resolve(assets, 'three-layer.js'));
copyFileSync(resolve(runtime, 'node_modules/three/LICENSE'), resolve(assets, 'THREE-LICENSE.txt'));
const manifest = {version: 1, three: '0.185.1', esbuild: '0.28.2', hyperframesVersion: cliVersion,
  browser, browserVersion, browserHash: sha(browser), hyperframes, node: realpathSync(process.execPath),
  nodeVersion: process.version, gpu: 'software', inputs, hyperframesHashes,
  assets: Object.fromEntries(['three-runtime.js', 'three-layer.js', 'THREE-LICENSE.txt'].map(name => [name, sha(resolve(assets, name))]))};
writeFileSync(marker, JSON.stringify(manifest, null, 2) + '\n', {flag: previous ? 'w' : 'wx'});
console.log(JSON.stringify({provisioned: true, runtime, three: manifest.three, browserVersion, hyperframesVersion: cliVersion, gpu: 'software'}));
