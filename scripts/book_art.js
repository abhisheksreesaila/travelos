// F-253: the book's drawn scenes. Reads the prototype's own drawing functions (docs/design/creators-v2/index.html, "const A = {" to "the books") and writes each scene as an SVG
// string to gitaway/bookart.json, with __G__ where the gradient id goes (the page puts a different one in each drawing). `node scripts/book_art.js --check` fails when the file is stale.
const fs = require('fs'), path = require('path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'docs/design/creators-v2/index.html'), 'utf8').split('\n');
const from = html.findIndex(l => l.startsWith('const A = {'));
const to = html.findIndex(l => l.startsWith('/* ================= the books'));
const src = html.slice(from, to).join('\n').replace("const g = 'a' + (++uid);", "const g = '__G__';");
const KEYS = ['lisbon', 'belem', 'alfama', 'sintra', 'kyoto', 'bigsur', 'amalfi', 'tahoe', 'cdmx', 'iceland'];
const art = new Function('uid', `${src}\nreturn art;`)(0);
const out = JSON.stringify(Object.fromEntries(KEYS.map(k => [k, art(k)])), null, 0) + '\n';
const file = path.join(root, 'gitaway/bookart.json');
if (process.argv.includes('--check')) { if (fs.readFileSync(file, 'utf8') !== out) { console.error('gitaway/bookart.json is stale: run node scripts/book_art.js'); process.exit(1); } }
else fs.writeFileSync(file, out);
