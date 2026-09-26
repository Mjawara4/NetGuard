import { readdirSync, statSync, readFileSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';

const ASSETS = 'dist/assets';
const INDEX_HTML = 'dist/index.html';
const MAX_ENTRY_KB = 350;

if (!existsSync(ASSETS)) {
    console.error(`Could not find ${ASSETS}. Run \`npm run build\` first.`);
    process.exit(1);
}

const files = readdirSync(ASSETS).filter((f) => f.endsWith('.js'));
if (files.length === 0) {
    console.error('No JS output found in dist/assets. Run `npm run build` first.');
    process.exit(1);
}

const sized = files
    .map((f) => ({ file: f, kb: statSync(join(ASSETS, f)).size / 1024 }))
    .sort((a, b) => b.kb - a.kb);

console.log(`chunks: ${sized.length}`);
for (const { file, kb } of sized) {
    console.log(`  ${kb.toFixed(1).padStart(8)} KB  ${file}`);
}

// Identify the entry chunk from dist/index.html rather than by filename
// convention. Rollup's chunk naming has no directory disambiguation for
// files literally named "index.*" (getAliasName is a plain basename minus
// extension), so an async route chunk resolving from e.g.
// pages/Hotspot/index.jsx can ALSO be emitted as "index-<hash>.js". Matching
// on the "index-" prefix over a size-sorted list can then pick the wrong
// file. The HTML's single <script type="module"> tag is the actual entry.
if (!existsSync(INDEX_HTML)) {
    console.error(`Could not find ${INDEX_HTML}. Run \`npm run build\` first.`);
    process.exit(1);
}

const html = readFileSync(INDEX_HTML, 'utf8');
const moduleScriptRe = /<script\b[^>]*\btype=["']module["'][^>]*>/gi;
const moduleScripts = html.match(moduleScriptRe) ?? [];

if (moduleScripts.length === 0) {
    console.error(`Found no <script type="module"> tag in ${INDEX_HTML}; cannot identify the entry chunk.`);
    process.exit(1);
}
if (moduleScripts.length > 1) {
    console.error(`Found ${moduleScripts.length} <script type="module"> tags in ${INDEX_HTML}; expected exactly one. Cannot identify the entry chunk unambiguously.`);
    process.exit(1);
}

const srcMatch = moduleScripts[0].match(/\bsrc=["']([^"']+)["']/i);
if (!srcMatch) {
    console.error(`The <script type="module"> tag in ${INDEX_HTML} has no src attribute; cannot identify the entry chunk.`);
    process.exit(1);
}

const entryFile = basename(srcMatch[1]);
const entry = sized.find((f) => f.file === entryFile);
if (!entry) {
    console.error(`${INDEX_HTML} references entry chunk "${entryFile}", but no such file was found in ${ASSETS}.`);
    process.exit(1);
}

console.log(`\nentry chunk: ${entry.file} — ${entry.kb.toFixed(1)} KB (budget ${MAX_ENTRY_KB} KB)`);

if (entry.kb > MAX_ENTRY_KB) {
    console.error(`FAIL: entry chunk ${entry.kb.toFixed(1)} KB exceeds ${MAX_ENTRY_KB} KB`);
    process.exit(1);
}
console.log('PASS');
