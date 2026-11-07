// Bundles src/diorama.js with a tree-shaken three.js r187 into core/diorama.js (a classic script: file:// pages can't load
// ES modules). Needs esbuild and three@0.187.0 from a scratch folder outside the repo:
//   mkdir -p ~/.cache/story3d-build && cd ~/.cache/story3d-build && npm i three@0.187.0 esbuild
//   node docs/design/cockpit/tools/build.mjs
import { createRequire } from 'node:module';
import { gzipSync, brotliCompressSync } from 'node:zlib';
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url)), root = join(here, '..');
const mods = process.env.COCKPIT_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
const esbuild = createRequire(join(mods, 'x.js'))('esbuild');
await esbuild.build({ entryPoints: [join(root, 'src/diorama.js')], outfile: join(root, 'core/diorama.js'), bundle: true, minify: true, format: 'iife',
  target: 'es2020', legalComments: 'inline', alias: { three: join(mods, 'three/build/three.module.js') }, logLevel: 'warning' });
const kb = (n) => (n / 1024).toFixed(1);
const size = (f) => { const b = readFileSync(join(root, f)); return `${f}: ${kb(b.length)} KB min · ${kb(gzipSync(b, { level: 9 }).length)} KB gzip · ${kb(brotliCompressSync(b).length)} KB brotli`; };
for (const f of ['core/diorama.js', 'data/dem.js', 'data/geo.js', 'img/relief-light.webp', 'img/relief-dark.webp']) console.log(size(f));
