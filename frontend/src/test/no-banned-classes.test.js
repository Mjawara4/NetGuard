import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import config from '../../tailwind.config.js';

// The repo-wide gate. `pages-tokenised.test.jsx` holds each migrated file to
// the same rules one file at a time; this one walks the whole tree, so a file
// nobody remembered to add to a list cannot escape.
//
// Two gaps in the gate as the plan originally wrote it, both closed here:
//
//   1. It globbed `.jsx?` only, so it never opened `index.css` -- which carried
//      seven raw palette classes (including the app's GLOBAL FOCUS RING) and
//      four raw hexes. A gate that cannot see a stylesheet is not repo-wide.
//   2. A raw hex bypasses a class-based gate completely. Recharts and React
//      Flow take literal colour values, not Tailwind classes, so hexes cannot
//      be banned outright -- but they must be TOKEN hexes. The allowlist below
//      is parsed out of `tailwind.config.js`; hardcoding it would rot the
//      moment a token changes.
const SOURCE_RE = /\.(jsx?|tsx?|css)$/;

function sourceFiles(dir, acc = []) {
    for (const entry of readdirSync(dir)) {
        const full = join(dir, entry);
        if (statSync(full).isDirectory()) {
            // The tests themselves quote banned classes on purpose.
            if (entry !== 'test' && entry !== '__tests__') sourceFiles(full, acc);
        } else if (SOURCE_RE.test(entry)) {
            acc.push(full);
        }
    }
    return acc;
}

const files = sourceFiles('src');

/** Every `file:line` whose line matches `re`. */
function offenders(re) {
    const hits = [];
    for (const file of files) {
        const lines = readFileSync(file, 'utf8').split('\n');
        lines.forEach((line, i) => {
            if (re.test(line)) hits.push(`${file}:${i + 1}`);
        });
    }
    return hits;
}

const PALETTE =
    'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|' +
    'teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose';

const BANNED = [
    // Any utility prefix reaches a colour -- `ring-offset-`, `decoration-`,
    // `placeholder:text-`, `divide-x-` -- so the family is banned wherever it
    // appears, not just behind the dozen prefixes the brief listed.
    [new RegExp(`[a-z](?:-[a-z]+)*-(?:${PALETTE})-\\d{2,3}\\b`), 'default palette class'],
    [/font-(black|extrabold)\b/, 'weight above 700'],
    [/tracking-(wide|wider|widest)\b|tracking-\[/, 'wide tracking'],
    // The spec's floor is 12px. That means every size below it, in px or rem,
    // not only the 10px and 11px the brief named.
    [/text-\[([0-9]|1[01])px\]/, 'sub-12px text'],
    [/text-\[0?\.\d+rem\]/, 'sub-12px text (rem)'],
    [/shadow-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)/, 'coloured shadow'],
    [/bg-gradient-to|bg-clip-text/, 'gradient text'],
];

describe('the app carries no banned classes', () => {
    // A walker that silently returns nothing would pass every assertion below.
    it('walks the whole source tree, stylesheets included', () => {
        expect(files.length).toBeGreaterThan(20);
        expect(files).toContain(join('src', 'index.css'));
        expect(files.some((f) => f.endsWith('.jsx'))).toBe(true);
        expect(files.every((f) => !f.includes(`${join('src', 'test')}`))).toBe(true);
    });

    for (const [re, name] of BANNED) {
        it(`no file uses ${name}`, () => {
            expect(offenders(re)).toEqual([]);
        });
    }

    // Zero, not "at most one". The wordmark exception the plan allowed went
    // unused -- the final wordmark is "NetGuard AI" in sentence case -- and an
    // unused exception is just a hole.
    it('uppercase appears nowhere, including on the wordmark', () => {
        expect(offenders(/\buppercase\b/)).toEqual([]);
    });
});

// ---------------------------------------------------------------------------
// The radius ladder
// ---------------------------------------------------------------------------

// `theme.borderRadius` (not `theme.extend.borderRadius`) REPLACES Tailwind's
// scale, so an off-ladder spelling emits nothing: a silently square corner with
// no error. Resolving every spelling against the config is stronger than a
// blocklist of the three sizes we happen to have deleted.
const LADDER = config.theme.borderRadius;
const SIDES = new Set(['t', 'r', 'b', 'l', 's', 'e', 'tl', 'tr', 'br', 'bl', 'ss', 'se', 'ee', 'es']);

/**
 * The ladder key a `rounded…` class resolves to, or null if it resolves to
 * nothing. Handles variants (`sm:`, `dark:`), `!important`, per-side and
 * per-corner spellings, and arbitrary values.
 */
export function radiusKey(token) {
    const base = token.split(':').pop().replace(/^!/, '');
    if (!base.startsWith('rounded')) return null;
    let rest = base.slice('rounded'.length);
    if (rest === '') return 'DEFAULT';
    if (!rest.startsWith('-')) return null;
    const parts = rest.slice(1).split('-');
    if (parts.length > 1 && SIDES.has(parts[0])) parts.shift();
    else if (parts.length === 1 && SIDES.has(parts[0])) return 'DEFAULT';
    const size = parts.join('-');
    return size === '' ? null : size;
}

export function resolves(token) {
    const key = radiusKey(token);
    return key !== null && Object.prototype.hasOwnProperty.call(LADDER, key);
}

const ROUNDED_TOKEN_RE = /[A-Za-z0-9_:![\]/.%-]*\brounded[A-Za-z0-9_:![\]/.%-]*/g;

describe('the radius ladder is locked', () => {
    it('is defined at theme level, not inside extend, and keeps DEFAULT', () => {
        expect(config.theme.borderRadius).toBeDefined();
        expect(config.theme.extend.borderRadius).toBeUndefined();
        // A bare `rounded` / `rounded-t` / `rounded-tl` resolves to DEFAULT and
        // the app has ten of them. Without this key all ten go square silently.
        expect(LADDER.DEFAULT).toBe('4px');
        expect(Object.keys(LADDER).sort()).toEqual(['DEFAULT', 'full', 'lg', 'md', 'none', 'sm']);
        // The VALUES are the spec's ladder, not just the key names. Asserting the
        // keys alone left the rungs free to drift: `lg` could quietly become 13px
        // and every other assertion here still passed.
        expect(LADDER).toEqual({
            none: '0',
            DEFAULT: '4px',
            sm: '4px',
            md: '8px',
            lg: '14px',
            full: '9999px',
        });
    });

    it('every rounded spelling under src/ resolves to a rung', () => {
        const unresolved = [];
        for (const file of files) {
            readFileSync(file, 'utf8')
                .split('\n')
                .forEach((line, i) => {
                    for (const token of line.match(ROUNDED_TOKEN_RE) || []) {
                        if (!resolves(token)) unresolved.push(`${file}:${i + 1} ${token}`);
                    }
                });
        }
        expect(unresolved).toEqual([]);
    });

    // A literal radius bypasses a class-based rule exactly the way a raw hex
    // does: Recharts' `contentStyle` takes CSS, not classes, and three of the
    // four tooltips in the app were already on 8px while SalesForecast's sat at
    // 12px -- off the ladder, invisible to every class assertion.
    it('every literal radius value is a rung too', () => {
        const allowed = new Set(Object.values(LADDER));
        const strays = [];
        for (const file of files) {
            readFileSync(file, 'utf8')
                .split('\n')
                .forEach((line, i) => {
                    const re = /border-?[Rr]adius'?"?\s*:\s*'?"?([0-9]+(?:px|rem|%)?|0)/g;
                    let m;
                    while ((m = re.exec(line)) !== null) {
                        if (!allowed.has(m[1])) strays.push(`${file}:${i + 1} ${m[1]}`);
                    }
                });
        }
        expect(strays).toEqual([]);
    });

    // Proof the resolver bites. `rounded-t-2xl` is here because it is exactly
    // what the per-file gate's `/rounded-(xl|2xl|3xl)/` missed: two live uses
    // (ResponsiveModal, AIChatParams) sat behind a side segment and would have
    // gone square the moment the ladder landed.
    it('rejects the spellings that no longer resolve', () => {
        for (const token of [
            'rounded-xl',
            'rounded-2xl',
            'rounded-3xl',
            'rounded-t-2xl',
            'md:rounded-b-3xl',
            'rounded-[32px]',
            'rounded-tl-[4px]',
        ]) {
            expect(resolves(token)).toBe(false);
        }
    });

    it('accepts every spelling on the ladder', () => {
        for (const token of [
            'rounded',
            'rounded-t',
            'rounded-tl',
            'rounded-sm',
            'rounded-md',
            'rounded-lg',
            'rounded-full',
            'rounded-tl-none',
            'sm:rounded-lg',
            'md:rounded-t-md',
            '!rounded-full',
        ]) {
            expect(resolves(token)).toBe(true);
        }
    });
});

// ---------------------------------------------------------------------------
// Raw hexes must be token hexes
// ---------------------------------------------------------------------------

function flatten(colors, acc = []) {
    for (const value of Object.values(colors || {})) {
        if (typeof value === 'string') acc.push(value);
        else if (value && typeof value === 'object') flatten(value, acc);
    }
    return acc;
}

/** `#abc` / `#aabbcc` / `#aabbccdd` -> `aabbcc`; anything else -> null. */
export function normaliseHex(hex) {
    const raw = hex.replace('#', '').toLowerCase();
    if (raw.length === 3 || raw.length === 4) {
        return raw
            .slice(0, 3)
            .split('')
            .map((c) => c + c)
            .join('');
    }
    if (raw.length === 6 || raw.length === 8) return raw.slice(0, 6);
    return null;
}

export const TOKEN_HEXES = new Set(
    flatten({ ...config.theme.colors, ...config.theme.extend.colors })
        .filter((v) => /^#[0-9a-fA-F]{3,8}$/.test(v))
        .map(normaliseHex),
);

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/g;

describe('every colour in the app comes from a token', () => {
    it('the allowlist is parsed from the config, not hardcoded', () => {
        // 11 ink + 5 signal + up/down/warn.
        expect(TOKEN_HEXES.size).toBe(19);
        expect(TOKEN_HEXES.has('7c3e9c')).toBe(true); // signal-600
        expect(TOKEN_HEXES.has('8b5cf6')).toBe(false); // violet-500
        expect(TOKEN_HEXES.has('2563eb')).toBe(false); // blue-600
    });

    it('no raw hex under src/ is outside the token set', () => {
        const strays = [];
        for (const file of files) {
            readFileSync(file, 'utf8')
                .split('\n')
                .forEach((line, i) => {
                    for (const hex of line.match(HEX_RE) || []) {
                        const norm = normaliseHex(hex);
                        if (norm === null || !TOKEN_HEXES.has(norm)) {
                            strays.push(`${file}:${i + 1} ${hex}`);
                        }
                    }
                });
        }
        expect(strays).toEqual([]);
    });

    it('catches shorthand and alpha spellings of a non-token colour', () => {
        // #ccc was a live one, on the printed voucher's cut line.
        expect(TOKEN_HEXES.has(normaliseHex('#ccc'))).toBe(false);
        expect(TOKEN_HEXES.has(normaliseHex('#8b5cf680'))).toBe(false);
        // …and still recognises a token written short or with alpha.
        expect(TOKEN_HEXES.has(normaliseHex('#7C3E9CFF'))).toBe(true);
        expect(normaliseHex('#abcde')).toBe(null);
    });
});
