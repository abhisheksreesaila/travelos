// Bundles the prototypes into classic scripts (a file:// page can't load ES modules): dist/page.js for the
// page and dist/<concept>.js for each world, with a tree-shaken three.js r187 inside (the vendored copy).
// Needs esbuild and three from a scratch folder outside the repo (the same one story3d uses):
//   mkdir -p ~/.cache/story3d-build && cd ~/.cache/story3d-build && npm i three@0.187.0 esbuild playwright
//   node docs/design/cover3d/tools/build.mjs
import { createRequire } from 'node:module';
import { gzipSync, brotliCompressSync, constants } from 'node:zlib';
import { readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const mods = process.env.COVER3D_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
const esbuild = createRequire(join(mods, 'x.js'))('esbuild');
const concepts = (process.argv[2] || 'a,b,c').split(',');
const entries = [['page', 'page.js'], ...concepts.map((c) => [c, `concept-${c}.js`])];
for (const [out, src] of entries) {
  try {
    await esbuild.build({
      entryPoints: [join(root, 'src', src)], outfile: join(root, 'dist', out + '.js'), bundle: true, minify: true, format: 'iife',
      target: 'es2020', legalComments: 'inline', alias: { three: join(mods, 'three/build/three.module.js') }, logLevel: 'warning',
    });
  } catch (e) { if (out === 'page') throw e; console.log('skip', out, e.message.split('\n')[0]); }
}
const size = (f) => { try { const b = readFileSync(join(root, 'dist', f + '.js')); return { raw: b.length, gz: gzipSync(b, { level: 9 }).length, br: brotliCompressSync(b, { params: { [constants.BROTLI_PARAM_QUALITY]: 11 } }).length }; } catch { return null; } };
const kb = (n) => (n / 1024).toFixed(1);
const page = size('page'), report = { page };
console.log(`page.js   ${kb(page.raw)} KB min · ${kb(page.gz)} KB gzip · ${kb(page.br)} KB brotli`);
for (const c of ['a', 'b', 'c']) {
  const s = size(c); if (!s) continue; report[c] = { ...s, totalGz: s.gz + page.gz, totalBr: s.br + page.br };
  console.log(`${c}.js      ${kb(s.raw)} KB min · ${kb(s.gz)} KB gzip · ${kb(s.br)} KB brotli · page total ${kb(s.gz + page.gz)} KB gzip`);
}
writeFileSync(join(root, 'dist', 'sizes.json'), JSON.stringify(report, null, 2) + '\n');
