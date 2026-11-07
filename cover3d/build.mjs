// Builds the cover's world (F-206). Two outputs, both under assets/ and loaded only by assets/js/cover.js on the signed-out landing:
//   assets/vendor/three-0.187.0/three.cover.min.js  three.js r187, tree-shaken to exactly the names src/ imports, with three's licence (LICENSE beside it)
//   assets/js/cover/world.js                         src/main.js and everything it imports, minified, importing three by the path above
// Then it prints the gzip and brotli sizes and writes them to sizes.json (tests/test_cover_budget.py checks the budget itself).
// Needs three@0.187.0 and esbuild@0.28.2 (package.json): `npm ci` here, or COVER3D_MODULES=<a node_modules with both>.
import { createRequire } from 'node:module';
import { existsSync, readFileSync, readdirSync, writeFileSync, mkdirSync, copyFileSync } from 'node:fs';
import { gzipSync, brotliCompressSync, constants } from 'node:zlib';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');
const mods = process.env.COVER3D_MODULES || [join(here, 'node_modules'), join(homedir(), '.cache/story3d-build/node_modules')].find((p) => existsSync(join(p, 'three')));
if (!mods) throw new Error('three and esbuild not found: run `npm ci` in cover3d/ or set COVER3D_MODULES');
const req = createRequire(join(mods, 'x.js'));
const esbuild = req('esbuild');
const pin = JSON.parse(readFileSync(join(here, 'package.json'), 'utf8'));
const threeVersion = JSON.parse(readFileSync(join(mods, 'three/package.json'), 'utf8')).version;
if (threeVersion !== pin.dependencies.three) throw new Error(`three ${threeVersion} found, ${pin.dependencies.three} pinned`);
const THREE_DIR = `assets/vendor/three-${threeVersion}`;
const THREE_URL = `/${THREE_DIR}/three.cover.min.js`;
const DEV = process.env.COVER3D_DEV === '1';     // unminified world with an inline source map, for debugging only; never commit a DEV build

// 1. every name src/ imports from 'three'
const names = new Set();
for (const f of readdirSync(join(here, 'src')).filter((f) => f.endsWith('.js'))) {
  const s = readFileSync(join(here, 'src', f), 'utf8');
  for (const m of s.matchAll(/import\s*\{([^}]*)\}\s*from\s*['"]three['"]/g)) m[1].split(',').map((x) => x.trim().split(/\s+as\s+/)[0]).filter(Boolean).forEach((n) => names.add(n));
}
const list = [...names].sort();

// 2. three, tree-shaken to those names
mkdirSync(join(repo, THREE_DIR), { recursive: true });
await esbuild.build({
  stdin: { contents: `export { ${list.join(', ')} } from 'three';`, resolveDir: here, loader: 'js' },
  outfile: join(repo, THREE_DIR, 'three.cover.min.js'), bundle: true, minify: true, format: 'esm', target: 'es2020',
  legalComments: 'inline', nodePaths: [mods], logLevel: 'warning',
});
copyFileSync(join(mods, 'three/LICENSE'), join(repo, THREE_DIR, 'LICENSE'));
writeFileSync(join(repo, THREE_DIR, 'README.md'), `# three.js ${threeVersion} (vendored for the cover, F-206)\n\n` +
  `\`three.cover.min.js\` is three.js r${threeVersion.split('.')[1]} from the npm package \`three@${threeVersion}\` (MIT, see LICENSE), tree-shaken by cover3d/build.mjs to the ${list.length} names the cover's world imports:\n\n${list.join(', ')}.\n\n` +
  'Do not edit it by hand: change cover3d/src and run `node cover3d/build.mjs`.\n');

// the sources' fingerprint goes in the bundle's banner, so a test can tell a world built from older sources (tests/test_cover_budget.py)
const srcHash = createHash('sha256');
for (const f of readdirSync(join(here, 'src')).filter((f) => f.endsWith('.js')).sort()) srcHash.update(f + '\n' + readFileSync(join(here, 'src', f), 'utf8').replace(/\r\n/g, '\n'));
const SRC = srcHash.digest('hex').slice(0, 16);

// 3. the world, with three left as an import of the vendored file
const external = { name: 'three-vendored', setup(b) { b.onResolve({ filter: /^three$/ }, () => ({ path: THREE_URL, external: true })); } };
await esbuild.build({
  entryPoints: [join(here, 'src/main.js')], outfile: join(repo, 'assets/js/cover/world.js'), bundle: true, minify: !DEV, sourcemap: DEV ? 'inline' : false, format: 'esm',
  target: 'es2020', legalComments: 'inline', plugins: [external], logLevel: 'warning',
  banner: { js: `/* GitAway cover world (F-206), built by cover3d/build.mjs from cover3d/src (src:${SRC}${DEV ? ' DEV' : ''}). Credits: cover3d/CREDITS.md */` },
});

// 4. sizes
const size = (p) => { const b = readFileSync(join(repo, p)); return { raw: b.length, gz: gzipSync(b, { level: 9 }).length, br: brotliCompressSync(b, { params: { [constants.BROTLI_PARAM_QUALITY]: 11 } }).length }; };
const out = { three: size(`${THREE_DIR}/three.cover.min.js`), world: size('assets/js/cover/world.js'), names: list.length };
const kb = (n) => (n / 1024).toFixed(1);
for (const k of ['three', 'world']) console.log(`${k.padEnd(6)} ${kb(out[k].raw)} KB min · ${kb(out[k].gz)} KB gzip · ${kb(out[k].br)} KB brotli`);
writeFileSync(join(here, 'sizes.json'), JSON.stringify(out, null, 2) + '\n');
