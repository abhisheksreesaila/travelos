// Bundles the prototypes into classic scripts (file:// can't load ES modules): dist/ui.js for the page and
// dist/<concept>.js for each scene with a tree-shaken three.js r187 inside (the vendored copy).
// Needs esbuild and three from a scratch folder outside the repo:
//   mkdir -p ~/.cache/story3d-build && cd ~/.cache/story3d-build && npm i three@0.187.0 esbuild
//   node docs/design/story3d/build.mjs
import { createRequire } from 'node:module';
import { gzipSync, brotliCompressSync } from 'node:zlib';
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const mods = process.env.STORY3D_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
const esbuild = createRequire(join(mods, 'x.js'))('esbuild');
const entries = ['ui', 'diorama', 'postcards', 'globe'];
for (const e of entries) {
  await esbuild.build({
    entryPoints: [join(here, 'src', e + '.js')], outfile: join(here, 'dist', e + '.js'), bundle: true, minify: true, format: 'iife',
    target: 'es2020', legalComments: 'inline', alias: { three: join(mods, 'three/build/three.module.js') }, logLevel: 'warning',
  });
}
const size = (f) => { const b = readFileSync(join(here, 'dist', f + '.js')); return { raw: b.length, gz: gzipSync(b, { level: 9 }).length, br: brotliCompressSync(b).length }; };
const ui = size('ui'); const kb = (n) => (n / 1024).toFixed(1);
console.log(`ui.js         ${kb(ui.raw)} KB min · ${kb(ui.gz)} KB gzip · ${kb(ui.br)} KB brotli`);
for (const e of entries.slice(1)) { const s = size(e); console.log(`${e.padEnd(13)} ${kb(s.raw)} KB min · ${kb(s.gz)} KB gzip · ${kb(s.br)} KB brotli · page total ${kb(s.gz + ui.gz)} KB gzip`); }
