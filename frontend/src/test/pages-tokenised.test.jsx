import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';

// Source-level assertions: these pages need heavy mocking to render, and
// what matters here is that no banned class survives anywhere in the file,
// including branches a render would not reach.
//
// Every pattern below is deliberately WIDER than the one in the task brief.
// Three gate gaps have already been found in this plan (a 6-family palette
// list against 15 families in use, a harness that graded pages it never
// loaded, and a size floor that covered 2 of the 5 sub-12px sizes actually
// present). A gate is worth its worst case, so each rule here is written to
// match the rule it enforces rather than the examples that prompted it.
const PALETTE = 'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose';

const banned = [
    // Any utility prefix, not just the dozen the brief listed: `ring-offset-`,
    // `decoration-`, `placeholder:text-`, `divide-x-` and friends all reach a
    // colour, and a raw palette family is banned wherever it appears.
    [new RegExp(`[a-z](?:-[a-z]+)*-(?:${PALETTE})-\\d{2,3}\\b`), 'default palette class'],
    // 900 and 800 are both outside the 400/500/600/700 ladder.
    [/font-(black|extrabold)\b/, 'weight above 700'],
    [/\buppercase\b/, 'uppercase'],
    // The spec removes widest/wider and allows no arbitrary tracking either.
    [/tracking-(wide|wider|widest)\b|tracking-\[/, 'wide tracking'],
    // The brief's regex only covered 10px and 11px. The repo also carries 7px,
    // 8px and 9px -- Layout.jsx's notification badge is one of them -- so this
    // matches every size under the spec's 12px floor, including rem spellings.
    [/text-\[([0-9]|1[01])px\]/, 'sub-12px text'],
    [/text-\[0?\.\d+rem\]/, 'sub-12px text (rem)'],
    [/shadow-blue/, 'coloured shadow'],
    [/bg-gradient-to|bg-clip-text/, 'gradient text'],
    // The radius ladder is sm/md/lg. Task 8 locks this down repo-wide; these
    // five files are migrated now, so hold them to it now.
    [/rounded-(xl|2xl|3xl)\b|rounded-\[/, 'off-ladder radius'],
];

export function assertTokenised(path) {
    const src = readFileSync(path, 'utf8');
    const found = banned.filter(([re]) => re.test(src)).map(([, name]) => name);
    return found;
}

// Review Focus #1, second half: a migration can silently drop the `dark:`
// half of a pair (`text-ink-400 dark:text-ink-500` -> `text-ink-400`), and
// every other test still passes while dark mode quietly degrades. Any file
// that styles colour at all must still carry dark variants.
export function hasDarkVariants(path) {
    const src = readFileSync(path, 'utf8');
    const stylesColour = /(bg|text|border)-(ink|signal)-/.test(src) || /-(up|down|warn)\b/.test(src);
    if (!stylesColour) return true;
    return /dark:/.test(src);
}

const pages = [
    'src/pages/Dashboard.jsx',
    'src/pages/Sites.jsx',
    'src/pages/Reports.jsx',
    'src/pages/NetworkMap.jsx',
    'src/components/Layout.jsx',
];

describe('tokenised pages', () => {
    for (const page of pages) {
        it(`${page} carries no banned classes`, () => {
            expect(assertTokenised(page)).toEqual([]);
        });

        it(`${page} keeps its dark-mode variants`, () => {
            expect(hasDarkVariants(page)).toBe(true);
        });
    }

    // The gate above can only see what it is given. These two assertions prove
    // the widened patterns actually bite, so a later "simplification" of the
    // regexes fails here instead of silently passing everything.
    it('the sub-12px rule catches 9px, not just 10-11px', () => {
        const [re] = banned.find(([, name]) => name === 'sub-12px text');
        for (const size of [7, 8, 9, 10, 11]) {
            expect(re.test(`text-[${size}px]`)).toBe(true);
        }
        expect(re.test('text-[12px]')).toBe(false);
    });

    it('the palette rule catches families behind any utility prefix', () => {
        const [re] = banned.find(([, name]) => name === 'default palette class');
        for (const cls of [
            'text-gray-400',
            'dark:placeholder:text-gray-600',
            'ring-offset-slate-200',
            'decoration-rose-500',
            'hover:divide-emerald-300',
        ]) {
            expect(re.test(cls)).toBe(true);
        }
        expect(re.test('text-ink-400')).toBe(false);
        expect(re.test('bg-signal-600')).toBe(false);
    });
});
