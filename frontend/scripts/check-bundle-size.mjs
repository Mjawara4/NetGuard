import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ASSETS = 'dist/assets';
const MAX_ENTRY_KB = 350;

const files = readdirSync(ASSETS).filter((f) => f.endsWith('.js'));
if (files.length === 0) {
    console.error('No JS output found in dist/assets. Run `npm run build` first.');
    process.exit(1);
}

const sized = files
    .map((f) => ({ file: f, kb: statSync(join(ASSETS, f)).size / 1024 }))
    .sort((a, b) => b.kb - a.kb);

// Vite names the entry chunk "index-<hash>.js".
const entry = sized.find((f) => f.file.startsWith('index-'));
if (!entry) {
    console.error('Could not identify the entry chunk (expected index-*.js).');
    process.exit(1);
}

console.log(`chunks: ${sized.length}`);
for (const { file, kb } of sized) {
    console.log(`  ${kb.toFixed(1).padStart(8)} KB  ${file}`);
}
console.log(`\nentry chunk: ${entry.kb.toFixed(1)} KB (budget ${MAX_ENTRY_KB} KB)`);

if (entry.kb > MAX_ENTRY_KB) {
    console.error(`FAIL: entry chunk ${entry.kb.toFixed(1)} KB exceeds ${MAX_ENTRY_KB} KB`);
    process.exit(1);
}
console.log('PASS');
