# NetGuard Visual Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the frontend's default-Tailwind palette and shouting typography with a deliberate token system, so the app stops reading as a 2022 SaaS template — without moving a single element.

**Architecture:** Tokens land in `tailwind.config.js` first. The UI kit in `components/ui/` is rebuilt against them, keeping its public API unchanged so existing pages keep working. Pages then migrate by *deleting* inline styling in favour of the kit. The radius lockdown comes last, because overriding Tailwind's `borderRadius` makes any surviving `rounded-2xl` emit nothing — a silent visual regression.

**Tech Stack:** Vite 5, React 18, Tailwind 3.4 (`darkMode: 'class'`), Vitest 1.6, @testing-library/react

**Spec:** `docs/superpowers/specs/2026-09-27-visual-identity-design.md`

## Global Constraints

- **No layout changes.** No element moves, resizes or repositions. This is colour, weight, size and radius only. A diff that moves a `<div>` is out of scope.
- Neutrals: custom `ink` scale (hue ≈175°, chroma ≤0.012) replaces Tailwind's `gray`. Exact values in the spec; copy them verbatim.
- Accent: `signal` violet, primary `#7C3E9C`. Replaces `blue-600`.
- Semantics: exactly three — `up #2F7D62`, `down #9A3A22`, `warn #8A6114`. No separate danger/success palette. Destructive actions are marked by weight and position, not a fourth red.
- `font-black` → **0 uses**. Weights are 400 / 500 / 600 / 700 only.
- `uppercase` → **0 uses**, with exactly one permitted exception: the `NetGuard` wordmark. `tracking-widest` → 0, no exceptions.
- Label floor **12px** (`text-xs`). `text-[10px]` → 0 uses.
- Radius ladder: `sm` 4px, `md` 8px, `lg` 14px. `rounded-full` survives only for circular things.
- One webfont: **Instrument Sans**, headings and numerals only; body stays `system-ui`. Subset latin, preloaded. **If the entry bundle passes ~110 KB, drop the webfont entirely and use system-ui** — the spec authorises that fallback.
- Frontend test baseline: **67 passing** (8 files) as of Task 3. None may regress. (Was 33/5 when this plan was written; Tasks 1-3 added the rest.)
- `npm run check:bundle` must keep passing its 350 KB entry budget.
- Text contrast ≥ 4.5:1 (3:1 at 24px+).
- Dark mode must keep working on every page.
- `/opt/netguard/frontend` is bind-mounted only for the *dev* server; the deployed frontend is built into its image, so nothing reaches production until an explicit rebuild. Work in a worktree regardless.
- node **is** installed on the host now (v24, added 2026-09-27 so Playwright could run), so `npx vitest run` works directly from `frontend/`. The containerized route still works if needed.
- `frontend/node_modules` is tracked in git and will be dirty after `npm install`. **Never `git add -A`.**

### Verification is measured in a browser, not asserted from source

**This applies to every task that changes how anything looks.** It was added
after Task 3 passed every source-level test while shipping a link at 1.14:1 and
placeholders at 1.70:1. Source greps prove a class is absent; they cannot prove
the result is legible.

Use `.superpowers/sdd/2026-09-27-visual-identity/verify/measure.mjs` with
`fixtures.json`. It drives headless Chromium, walks every rendered text node
*including form values and `::placeholder`*, composites the full ancestor alpha
stack, and compares computed colours at WCAG thresholds.

```bash
cp .superpowers/sdd/2026-09-27-visual-identity/verify/measure.mjs \
   .superpowers/sdd/2026-09-27-visual-identity/verify/fixtures.json /tmp/pwshot/
cd /tmp/pwshot && node measure.mjs http://127.0.0.1:5199 <route> <label> [--public] [--min-nodes=N]
```

Non-negotiables, each learned from a failure:

- **Playwright resolves only from `/tmp/pwshot`.** Do not add it as a repo dependency.
- **`verify/check.mjs` is retired.** It could not authenticate, so on any protected
  route it measured the login page under the requested label — the completely
  unmigrated Dashboard reported "0 contrast failure(s)". It also read `rgba` as
  opaque, giving every semantic wash a fictional ratio, and it never sampled
  inputs, which is how the 1.70:1 placeholders passed.
- **`--public`** for `/login` and `/signup`; everything else needs the seeded
  token. Dashboard is at `/`, not `/dashboard`.
- **`--min-nodes`** just under the page's current node count. A page that renders
  nothing must not be able to report success.
- **Restart the dev server after any `tailwind.config.js` edit.** Vite does not
  pick up theme keys via HMR and will serve stale CSS. Confirm with
  `curl -sS http://127.0.0.1:5199/src/index.css | grep -c <new-token>`.
- **Both themes, zero failures, before you commit.**

`.superpowers/sdd/**` is gitignored, so this tooling is not in version control.
If it should outlive the branch it needs a home under `frontend/scripts/`.
- Commits local only. Never push — the remote carries a plaintext PAT.

### The substitution table

Every migration task applies exactly this, and nothing else. It is here rather than in one task because tasks may be read out of order.

**Measured scale of the job**, counted across pages, Hotspot and shared components: `gray` ~1,017, `red` 134, `blue` 87, `emerald` 35, `purple` 28, `orange` 22, `pink` 12, `cyan` 12, `amber` 11, `yellow` 9, `green` 8, `violet` 1. `red` is the second-largest family and is mostly alert and destructive-action styling — it all collapses to the single `down` token.

| From | To |
|---|---|
| `gray-N` **used as a background or border** | `ink-N` at the same lightness position |
| `gray-N` **used as TEXT** | **Not a same-position swap — see the text rules below.** A mechanical swap preserves whatever contrast bug was already there. |
| `blue-*`, `indigo-*` | `signal-*` |
| `emerald-*`, `green-*` | `up` |
| `red-*` | `down` |
| `amber-*`, `orange-*`, `yellow-*` | `warn` |
| `purple-*`, `violet-*`, `fuchsia-*`, `pink-*`, `rose-*`, `cyan-*`, `sky-*`, `teal-*`, `lime-*` | `signal-*` where the element is interactive or branded; `ink-400` where it is purely decorative. The spec allows **one** accent and **three** semantics — a decorative hue has no home in it. |
| `slate-*`, `zinc-*`, `neutral-*`, `stone-*` | `ink-*` at the same lightness position |
| `font-black` | `font-semibold` on headings, `font-bold` on numerals |
| `uppercase`, `tracking-widest`, `tracking-wider` | removed |
| `text-[10px]`, `text-[11px]` | `text-xs` |
| `rounded-2xl`, `rounded-3xl`, `rounded-xl` | `rounded-md` |
| `rounded-lg` | `rounded-md` on cards and buttons, `rounded-sm` on inputs and badges |
| `rounded-full` | **left alone** |
| `shadow-blue*`, any coloured shadow | removed; a card gains `border border-ink-200 dark:border-ink-800` instead, because borders survive dark mode better than shadows |
| gradient wordmark (`bg-gradient-to-*` + `bg-clip-text`) | plain `font-display font-semibold` text |

### Text colour rules — measured, not guessed

A same-position swap preserves existing contrast bugs. These were computed against the real tokens, and the rendered login page proved the point: after a faithful same-position migration it still had 8 WCAG failures, one of them a *regression*.

| Role | Light | Dark | Why |
|---|---|---|---|
| Body / primary text | `text-ink-900` | `dark:text-ink-100` | 15.64 / 14.42 |
| Caption, label, muted, placeholder | `text-ink-500` | `dark:text-ink-400` | 4.62 / 6.04 |
| Link or accent text | `text-signal-600` | `dark:text-signal-300` | 6.51 / 5.94 |
| Text on a semantic wash | `text-ink-900` | `dark:text-ink-50` | semantic-coloured text on a semantic wash tops out at 2.39–3.36 in dark and cannot be rescued at any alpha |

**The `dark:` half moves in the OPPOSITE direction to the light half.** On a light ground text must be *darker*; on a dark ground it must be *lighter*. The existing code says `text-gray-400 dark:text-gray-500` — lighter on light, darker on dark, wrong on both counts. Inverting that pair is the single highest-value change in this plan.

**Tokens that FAIL as text and must never be used for it:** `ink-300` (1.70 on light) and `ink-400` (2.59 on light); `ink-500` on a dark ground (3.38). `signal-600` on a dark ground is 2.40 — the accent must drop to a light shade in dark mode, including in a wordmark.

**`signal-300` `#BB86D4` exists because `signal-400` is not light enough on a card.** Cards use `dark:bg-ink-800`, not the page's `ink-900`, and `signal-400` measures only 3.65 there. `signal-300` clears both dark grounds — 4.66 on `ink-800`, 5.94 on `ink-900` — so it is the single dark-mode accent-text token everywhere, with no "which ground am I on" rule to get wrong. It is deliberately the *least* light shade that passes, so it still reads as violet rather than pale lavender. It fails on light (2.63) and must never be used there.

**Watch for transition artifacts when measuring.** Both auth pages carried dead `animate-in` classes with no matching plugin, but `duration-700` still set `transition-duration` with `transition-property: all` — so toggling the `dark` class cross-faded every colour for 700ms and any measurement taken sooner read a half-blended value. The harness now waits 1000ms. If a page shows implausible near-miss failures, check for stray duration classes before believing them.

**Every `dark:` variant is preserved.** When you change `text-gray-400 dark:text-gray-500`, both halves move: `text-ink-400 dark:text-ink-500`. Dropping the `dark:` half is the easiest silent regression in this whole plan, and Task 4's gate checks for it.

**Nothing else changes.** No markup structure, no props, no spacing, padding, flex, grid, width or position class.

## Review Focus

Five things the spec implies that no task's own happy-path tests would exercise, most likely to bite first:

1. **Dark mode with the new neutrals.** A token swap can look correct in light and muddy in dark; the `ink` scale is where that shows. Test added in Task 2 (kit renders in both themes) and re-checked per page.
2. **Caption contrast.** `ink-400` on `ink-50` is the pair most likely to fail 4.5:1. A computed contrast test lands in Task 1 so it fails at the config, not in review.
3. **The webfont failing to load** — offline, blocked, or slow. Headings fall back to `system-ui` with different metrics; text can reflow or clip. Test added in Task 1.
4. **A voucher profile with no band colour.** The colour-band idea maps profiles to colours; a fourth profile, or a renamed one, falls off the map. Must degrade to a neutral band, not an invisible one or a crash. Test added in Task 7.
5. **A surviving `rounded-2xl` after the radius lockdown.** Tailwind emits nothing for an unknown class, so the corner silently goes sharp with no error anywhere. Guarded by the grep gate in Task 8, which is why the lockdown is last.

---

### Task 1: Tokens and the contrast gate

**Files:**
- Modify: `frontend/tailwind.config.js`
- Create: `frontend/src/test/tokens.test.js`

**Interfaces:**
- Produces: Tailwind colour keys `ink.{50…950}`, `signal.{400,500,600,700}`, `up`, `down`, `warn`; `fontFamily.display`. Every later task consumes these by class name (`bg-ink-50`, `text-signal-600`). Radii are NOT changed in this task — see Task 8.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/test/tokens.test.js`:

```js
import { describe, it, expect } from 'vitest';
import config from '../../tailwind.config.js';

const colors = config.theme.extend.colors;

// WCAG relative luminance, then contrast ratio. Written out rather than
// pulled from a dependency so the gate has no install cost.
function luminance(hex) {
  const c = hex.replace('#', '');
  const channels = [0, 2, 4].map((i) => {
    const v = parseInt(c.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('colour tokens', () => {
  it('defines the full ink scale', () => {
    for (const step of [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]) {
      expect(colors.ink[step]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('defines the signal accent and the three semantics', () => {
    expect(colors.signal[600]).toBe('#7C3E9C');
    expect(colors.up).toBe('#2F7D62');
    expect(colors.down).toBe('#9A3A22');
    expect(colors.warn).toBe('#8A6114');
  });

  it('has no leftover default gray or blue aliases', () => {
    expect(colors.gray).toBeUndefined();
    expect(colors.blue).toBeUndefined();
  });
});

describe('contrast', () => {
  // Review Focus #2: caption grey on the page ground is the pair that
  // fails most often, so it is pinned here rather than caught in review.
  it('caption text on the light ground meets 4.5:1', () => {
    expect(contrast(colors.ink[500], colors.ink[50])).toBeGreaterThanOrEqual(4.5);
  });

  it('body text on the light ground meets 4.5:1', () => {
    expect(contrast(colors.ink[900], colors.ink[50])).toBeGreaterThanOrEqual(4.5);
  });

  it('body text on the dark ground meets 4.5:1', () => {
    expect(contrast(colors.ink[100], colors.ink[950])).toBeGreaterThanOrEqual(4.5);
  });

  it('white on the accent meets 4.5:1, so primary buttons are readable', () => {
    expect(contrast('#FFFFFF', colors.signal[600])).toBeGreaterThanOrEqual(4.5);
  });

  it('each status colour is distinguishable from the ground', () => {
    for (const status of [colors.up, colors.down, colors.warn]) {
      expect(contrast(status, colors.ink[50])).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('up and down differ in lightness, not hue alone', () => {
    // Colour-blind safety: the spec requires a lightness difference.
    const delta = Math.abs(luminance(colors.up) - luminance(colors.down));
    expect(delta).toBeGreaterThan(0.04);
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd <worktree> && docker run --rm -v $PWD/frontend:/app -w /app node:18-alpine npm test -- src/test/tokens.test.js
```

Expected: FAIL — `colors` is undefined, since `tailwind.config.js` currently extends only spacing.

- [ ] **Step 3: Add the tokens**

In `frontend/tailwind.config.js`, inside `theme.extend`, add alongside the existing `padding`/`margin`/`height` keys — do not remove those, they carry the safe-area insets the mobile layout needs:

```js
            colors: {
                ink: {
                    50:  '#F6F8F7',
                    100: '#ECEFEE',
                    200: '#D9DEDC',
                    300: '#BAC2BF',
                    400: '#939E9A',
                    500: '#67736F',
                    600: '#55605D',
                    700: '#424B49',
                    800: '#2B3231',
                    900: '#1A1F1E',
                    950: '#101413',
                },
                signal: {
                    400: '#A971C4',
                    500: '#8F4FAF',
                    600: '#7C3E9C',
                    700: '#653180',
                },
                up:   '#2F7D62',
                down: '#9A3A22',
                warn: '#8A6114',
            },
            fontFamily: {
                display: ['"Instrument Sans"', 'system-ui', 'sans-serif'],
            },
```

- [ ] **Step 4: Run the test**

Expected: PASS. **If a contrast assertion fails, darken the token rather than lowering the threshold** — the threshold is the requirement. Report which token you moved and to what.

- [ ] **Step 5: Add the webfont with a fallback guard**

Add to `frontend/index.html`, in `<head>`:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@500;600;700&display=swap">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@500;600;700&display=swap">
```

`display=swap` is the Review Focus #3 mitigation: text paints in `system-ui` immediately and swaps when the font arrives, so a blocked or slow font never leaves the page blank. The `fontFamily.display` stack lists `system-ui` as its fallback for the same reason.

Add to `frontend/src/test/tokens.test.js`:

```js
describe('display font', () => {
  // Review Focus #3: a blocked or slow webfont must degrade, not break.
  it('falls back to a system face', () => {
    expect(config.theme.extend.fontFamily.display).toContain('system-ui');
  });
});
```

- [ ] **Step 6: Measure the bundle cost the spec asked for**

```bash
cd <worktree> && docker run --rm -v $PWD/frontend:/app -w /app node:18-alpine sh -c 'npm run build && npm run check:bundle'
```

Expected: PASS. **Record the entry-chunk size.** The spec's fallback trigger is ~110 KB: if the entry passes it, remove the font links and the `display` family, and report that you took the documented fallback. The font is loaded from a stylesheet rather than bundled, so the entry should barely move — say what you actually measured rather than assuming.

- [ ] **Step 7: Commit**

```bash
git add frontend/tailwind.config.js frontend/index.html frontend/src/test/tokens.test.js
git commit -m "feat(frontend): add ink/signal design tokens with a contrast gate"
```

---

### Task 2: Rebuild the UI kit against the tokens

The kit is the enforcement point: once `StatCard` owns the numeral treatment, every page using it loses its `font-black`/`text-[10px]` pairing for free.

**Files:**
- Modify: `frontend/src/components/ui/Button.jsx`, `Card.jsx`, `StatCard.jsx`, `Badge.jsx`, `Input.jsx`, `PageHeader.jsx`, `Skeleton.jsx`
- Create: `frontend/src/test/ui-kit.test.jsx`

**Interfaces:**
- Consumes: the Task 1 tokens.
- Produces: the same component API as today — **no prop is added, renamed or removed**, so pages keep working unchanged. Read each component's current props before touching it and preserve them exactly.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/test/ui-kit.test.jsx`:

```jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { Button, Card, StatCard, Badge, Input } from '../components/ui';

describe('UI kit after tokenisation', () => {
  it('a primary button uses the accent, not default blue', () => {
    const { container } = render(<Button>Save changes</Button>);
    const html = container.innerHTML;
    expect(html).not.toMatch(/blue-\d/);
    expect(html).toMatch(/signal-600/);
  });

  it('no kit component uses font-black or uppercase', () => {
    const { container } = render(
      <div>
        <Button>Save changes</Button>
        <Card><span>body</span></Card>
        <StatCard label="Active sessions" value="38" />
        <Badge>Online</Badge>
      </div>
    );
    expect(container.innerHTML).not.toMatch(/font-black/);
    expect(container.innerHTML).not.toMatch(/uppercase/);
    expect(container.innerHTML).not.toMatch(/tracking-widest/);
  });

  it('no kit component uses a 10px label', () => {
    const { container } = render(<StatCard label="Active sessions" value="38" />);
    expect(container.innerHTML).not.toMatch(/text-\[10px\]/);
  });

  it('StatCard still renders its label and value', () => {
    render(<StatCard label="Active sessions" value="38" />);
    expect(screen.getByText('Active sessions')).toBeInTheDocument();
    expect(screen.getByText('38')).toBeInTheDocument();
  });

  it('numerals are tabular so columns of figures line up', () => {
    const { container } = render(<StatCard label="Vouchers" value="11,237" />);
    expect(container.innerHTML).toMatch(/tabular-nums/);
  });

  it('Input still associates its label with its control', () => {
    render(<Input id="qty" label="How many" />);
    expect(screen.getByLabelText('How many')).toBeInTheDocument();
  });

  // Review Focus #1: a token swap can look right in light and wrong in dark.
  it('renders under the dark class without throwing', () => {
    const { container } = render(
      <div className="dark">
        <Card><StatCard label="Active sessions" value="38" /></Card>
      </div>
    );
    expect(container.querySelector('.dark')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

Expected: FAIL — the kit currently emits `blue-*`, `font-black`, `uppercase` and `text-[10px]`. `Input` may also fail the label association; if so that is a real pre-existing bug and fixing it is in scope here.

- [ ] **Step 3: Rebuild each component**

Read each file first, then apply **the substitution table in Global Constraints** — colour, weight, size and radius only.

The config still defines the old radii until Task 8, so nothing breaks mid-migration.

One addition specific to the kit: `StatCard`'s value gains `tabular-nums font-bold font-display`, which is what removes the `font-black`/`text-[10px]` pairing from every page that uses it.

- [ ] **Step 4: Run the full suite**

Expected: the 6 new tests pass and all 33 pre-existing tests still pass — the kit's API is unchanged, so route and shell tests should be unaffected. If a pre-existing test fails, you changed an API; revert that part.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui frontend/src/test/ui-kit.test.jsx
git commit -m "feat(frontend): rebuild the UI kit against design tokens"
```

---

### Task 3: Login and Signup, plus the label fix

Smallest surface, and the right place for the accessibility bug.

**Files:**
- Modify: `frontend/src/pages/Login.jsx`, `frontend/src/pages/Signup.jsx`
- Create: `frontend/src/test/auth-pages.test.jsx`

**Interfaces:**
- Consumes: Task 1 tokens, Task 2 kit.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/test/auth-pages.test.jsx`:

```jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

vi.mock('../api', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn(() => Promise.resolve({ data: {} })) },
}));

import Login from '../pages/Login.jsx';

describe('Login', () => {
  // The labels currently have no htmlFor and the inputs no id, so a screen
  // reader announces nothing. This is the fix.
  it('associates every label with its control', () => {
    render(<MemoryRouter><Login /></MemoryRouter>);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('uses no default-palette or shouting classes', () => {
    const { container } = render(<MemoryRouter><Login /></MemoryRouter>);
    const html = container.innerHTML;
    expect(html).not.toMatch(/(bg|text|border|from|to|ring|divide)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d/);
    expect(html).not.toMatch(/font-black|uppercase|tracking-widest|text-\[10px\]/);
  });

  it('has no gradient wordmark', () => {
    const { container } = render(<MemoryRouter><Login /></MemoryRouter>);
    expect(container.innerHTML).not.toMatch(/bg-gradient-to|bg-clip-text/);
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

Expected: FAIL on all three — the labels are unassociated, the palette is default, and Login carries gradient text.

- [ ] **Step 3: Fix both pages**

Add `id` to each input and the matching `htmlFor` to its label. Then apply **the substitution table in Global Constraints**. Replace the gradient wordmark with plain `font-display font-semibold text-ink-900 dark:text-ink-50` text — the spec permits `uppercase` here if the wordmark wants it, and nowhere else.

- [ ] **Step 4: Run the suite** — expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Login.jsx frontend/src/pages/Signup.jsx frontend/src/test/auth-pages.test.jsx
git commit -m "feat(frontend): tokenise auth pages and fix label associations"
```

---

### Task 4: Dashboard, Sites, Reports, NetworkMap

Four pages of the same shape — batched deliberately, because each is the same mechanical substitution and a reviewer would accept or reject them together.

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`, `Sites.jsx`, `Reports.jsx`, `NetworkMap.jsx`
- Modify: `frontend/src/components/Layout.jsx` (the shell's gradient wordmark and nav colours)
- Create: `frontend/src/test/pages-tokenised.test.jsx`

**Interfaces:**
- Consumes: Task 1 tokens, Task 2 kit.
- Produces: the shared `assertTokenised` helper the next task reuses.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/test/pages-tokenised.test.jsx`:

```jsx
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';

// Source-level assertions: these pages need heavy mocking to render, and
// what matters here is that no banned class survives anywhere in the file,
// including branches a render would not reach.
export function assertTokenised(path) {
  const src = readFileSync(path, 'utf8');
  const banned = [
    [/(bg|text|border|from|to|ring|divide|outline|shadow|accent|caret|fill|stroke)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d/, 'default palette class'],
    [/font-black/, 'font-black'],
    [/uppercase/, 'uppercase'],
    [/tracking-wide(r|st)/, 'wide tracking'],
    [/text-\[1[01]px\]/, '10-11px text'],
    [/shadow-blue/, 'coloured shadow'],
    [/bg-gradient-to|bg-clip-text/, 'gradient text'],
  ];
  const found = banned.filter(([re]) => re.test(src)).map(([, name]) => name);
  return found;
}

// Review Focus #1, second half: a migration can silently drop the `dark:`
// half of a pair (`text-ink-400 dark:text-ink-500` → `text-ink-400`), and
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
});
```

- [ ] **Step 2: Run it to confirm it fails**

Expected: FAIL for all five, listing which banned classes each still carries. That list is your worklist.

- [ ] **Step 3: Migrate the five files**

Apply **the substitution table in Global Constraints**. Where a page hand-rolls a card or stat that the kit already provides, replace it with the kit component — that is the "migration reduces code" part. **Do not change any layout, spacing or flex class.** `Layout.jsx` loses the gradient wordmark and its `blue-600` hovers.

- [ ] **Step 4: Run the suite** — expected: all pass, including the pre-existing route and shell tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx frontend/src/pages/Sites.jsx frontend/src/pages/Reports.jsx frontend/src/pages/NetworkMap.jsx frontend/src/components/Layout.jsx frontend/src/test/pages-tokenised.test.jsx
git commit -m "feat(frontend): tokenise dashboard, sites, reports, network map and shell"
```

---

### Task 5: Devices, Settings, AdminDashboard

**Files:**
- Modify: `frontend/src/pages/Devices.jsx`, `Settings.jsx`, `AdminDashboard.jsx`
- Modify: `frontend/src/components/ResponsiveTable.jsx`, `ResponsiveModal.jsx`, `ProtectedRoute.jsx`, `SalesForecast.jsx`, `AIChatParams.jsx`
- Modify: `frontend/src/test/pages-tokenised.test.jsx` (extend the list)

**Interfaces:**
- Consumes: `assertTokenised` from Task 4.
- Produces: nothing new.

- [ ] **Step 1: Extend the test list**

Add to the `pages` array in `frontend/src/test/pages-tokenised.test.jsx`:

```js
  'src/pages/Devices.jsx',
  'src/pages/Settings.jsx',
  'src/pages/AdminDashboard.jsx',
  'src/components/ResponsiveTable.jsx',
  'src/components/ResponsiveModal.jsx',
  'src/components/ProtectedRoute.jsx',
  'src/components/SalesForecast.jsx',
  'src/components/AIChatParams.jsx',
```

- [ ] **Step 2: Run it to confirm the new entries fail** — expected: 8 new failures with their banned-class lists.

- [ ] **Step 3: Migrate them** — apply **the substitution table in Global Constraints**. `SalesForecast.jsx` draws a chart: its series colours become `signal-600` and `ink-400`, and it must stay distinguishable in dark mode.

- [ ] **Step 4: Run the suite** — expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Devices.jsx frontend/src/pages/Settings.jsx frontend/src/pages/AdminDashboard.jsx frontend/src/components frontend/src/test/pages-tokenised.test.jsx
git commit -m "feat(frontend): tokenise devices, settings, admin and shared components"
```

---

### Task 6: Extract the Hotspot tab panels

Structural only. **No styling changes in this task** — a move and a restyle in one commit is unreviewable.

**Files:**
- Create: `frontend/src/pages/Hotspot/panels/UsersPanel.jsx`, `ActivePanel.jsx`, `ProfilesPanel.jsx`, `GeneratorPanel.jsx`, `BooksPanel.jsx`, `LogsPanel.jsx`, `ReportsPanel.jsx`
- Modify: `frontend/src/pages/Hotspot/index.jsx` (2,178 lines)

**Interfaces:**
- Produces: each panel as a default-exported component taking its data and handlers as props. `index.jsx` keeps **all** state, data fetching, polling and tab routing — panels are presentational. Their exact prop lists come from what each `activeTab === '…'` block currently reads from scope; derive them from the source, do not invent them.

- [ ] **Step 1: Confirm the current tests pass before touching anything**

```bash
cd <worktree> && docker run --rm -v $PWD/frontend:/app -w /app node:18-alpine npm test
```

Expected: PASS. Record the count. This is the "did I break it" baseline, and the existing `VoucherJob.test.jsx` covers the generator and books flows — the two panels most at risk.

- [ ] **Step 2: Extract one panel and verify**

Start with `LogsPanel` — the simplest, fewest props. Move its JSX verbatim, pass what it read from scope as props, render it from `index.jsx` where the block was. Run the suite. Expected: PASS, same count.

- [ ] **Step 3: Extract the remaining six, one at a time, running the suite after each**

Do them in ascending order of complexity: Logs, Reports, Profiles, Active, Users, Books, Generator. **Run the full suite after every single one.** If a panel's extraction breaks a test, that panel had hidden coupling to state — revert just that panel and report it rather than rewiring state to suit the move.

Generator and Books are last because `VoucherJob.test.jsx` exercises their polling, resume and reprint behaviour; they carry the most props and the most risk.

- [ ] **Step 4: Confirm index.jsx actually shrank**

```bash
wc -l frontend/src/pages/Hotspot/index.jsx frontend/src/pages/Hotspot/panels/*.jsx
```

Expected: `index.jsx` well under 1,000 lines, each panel a few hundred at most. Report the before and after.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Hotspot
git commit -m "refactor(frontend): extract Hotspot tab panels, no behaviour change"
```

---

### Task 7: Tokenise Hotspot, and the profile colour band

**Files:**
- Modify: `frontend/src/pages/Hotspot/index.jsx`, `frontend/src/pages/Hotspot/components.jsx`, all seven files under `panels/`
- Create: `frontend/src/pages/Hotspot/profileBand.js`
- Create: `frontend/src/test/profile-band.test.js`
- Modify: `frontend/src/test/pages-tokenised.test.jsx` (extend the list)

**Interfaces:**
- Consumes: Task 1 tokens, Task 6 panels.
- Produces: `bandFor(profileName) -> string` — a Tailwind background class. Used by `ProfilesPanel`, `GeneratorPanel` and `BooksPanel`.

- [ ] **Step 1: Write the failing test for the band**

Create `frontend/src/test/profile-band.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { bandFor } from '../pages/Hotspot/profileBand.js';

describe('profile colour band', () => {
  it('gives the known profiles stable, distinct colours', () => {
    const a = bandFor('default');
    const b = bandFor('day-pass');
    const c = bandFor('week');
    expect(new Set([a, b, c]).size).toBe(3);
    expect(bandFor('default')).toBe(a); // stable across calls
  });

  // Review Focus #4: a fourth profile, or a renamed one, must not vanish.
  it('gives an unknown profile a visible neutral band', () => {
    const band = bandFor('some-new-profile');
    expect(band).toBeTruthy();
    expect(band).toMatch(/ink-/);
  });

  it('survives a missing or empty profile name', () => {
    expect(bandFor(undefined)).toBeTruthy();
    expect(bandFor('')).toBeTruthy();
    expect(bandFor(null)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run it to confirm it fails** — expected: module not found.

- [ ] **Step 3: Implement the band**

Create `frontend/src/pages/Hotspot/profileBand.js`:

```js
// A voucher profile's colour band, the way denominations are coded on
// prepaid cards: it lets an operator tell profiles apart at a glance
// without reading. The colour is data, not decoration, so it is the same
// everywhere a profile appears.
//
// An unknown profile gets a neutral band rather than nothing — a router
// can hold profiles this map has never seen, and an invisible band would
// read as "no profile" instead of "a profile I don't have a colour for".

const BANDS = {
  'default': 'bg-signal-600',
  'day-pass': 'bg-up',
  'week': 'bg-warn',
};

const FALLBACK = 'bg-ink-400';

export function bandFor(profileName) {
  if (!profileName) return FALLBACK;
  return BANDS[profileName] ?? FALLBACK;
}
```

- [ ] **Step 4: Run the test** — expected: PASS, 3 tests.

- [ ] **Step 5: Extend the source gate to Hotspot**

Add to the `pages` array in `frontend/src/test/pages-tokenised.test.jsx`:

```js
  'src/pages/Hotspot/index.jsx',
  'src/pages/Hotspot/components.jsx',
  'src/pages/Hotspot/panels/UsersPanel.jsx',
  'src/pages/Hotspot/panels/ActivePanel.jsx',
  'src/pages/Hotspot/panels/ProfilesPanel.jsx',
  'src/pages/Hotspot/panels/GeneratorPanel.jsx',
  'src/pages/Hotspot/panels/BooksPanel.jsx',
  'src/pages/Hotspot/panels/LogsPanel.jsx',
  'src/pages/Hotspot/panels/ReportsPanel.jsx',
```

Run it. Expected: 9 failures listing banned classes per file — Hotspot is where most of the 222 `font-black` and 210 `uppercase` live.

- [ ] **Step 6: Migrate the Hotspot files**

Apply **the substitution table in Global Constraints**. Additionally:

- Apply `bandFor(profile)` as a 5px-wide element where a profile is named in `ProfilesPanel`, `GeneratorPanel` and `BooksPanel`.
- Voucher codes, IP addresses and durations get `font-mono`. **Labels do not** — mono on a label was the specific tell the rejected mockups hit.
- Rename the operator-facing copy the spec asks for: "Generate" → "Print", "batch" → "book", history actions keep "Reprint". **Copy only — no state, handler or endpoint names change.**

- [ ] **Step 7: Run the full suite**

Expected: all pass, including `VoucherJob.test.jsx`. If a voucher test fails on changed copy, update the test's expected string — the copy change is intended. Say which strings you changed.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Hotspot frontend/src/test/profile-band.test.js frontend/src/test/pages-tokenised.test.jsx
git commit -m "feat(frontend): tokenise hotspot, add profile colour bands and counter copy"
```

---

### Task 8: Lock the radius ladder and gate the whole app

Last, because overriding `borderRadius` makes any surviving `rounded-2xl` emit **nothing** — a silently sharp corner with no error. The grep gate must pass before the lockdown lands.

**Files:**
- Modify: `frontend/tailwind.config.js`
- Create: `frontend/src/test/no-banned-classes.test.js`

**Interfaces:**
- Consumes: everything above.
- Produces: the repo-wide gate.

- [ ] **Step 1: Write the repo-wide gate**

Create `frontend/src/test/no-banned-classes.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

function sourceFiles(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry !== 'test') sourceFiles(full, acc);
    } else if (/\.jsx?$/.test(entry)) {
      acc.push(full);
    }
  }
  return acc;
}

const files = sourceFiles('src');

// The spec's acceptance test, as a test rather than a promise.
const BANNED = [
  [/font-black/, 'font-black'],
  [/tracking-wide(r|st)/, 'wide tracking'],
  [/text-\[1[01]px\]/, '10-11px text'],
  [/rounded-(2xl|3xl|xl)/, 'a removed radius'],
  [/shadow-blue/, 'coloured shadow'],
  [/bg-gradient-to|bg-clip-text/, 'gradient text'],
  [/(bg|text|border|from|to|ring|divide|outline|shadow|accent|caret|fill|stroke)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d/, 'default palette class'],
];

describe('the app carries no banned classes', () => {
  for (const [re, name] of BANNED) {
    it(`no file uses ${name}`, () => {
      const offenders = files.filter((f) => re.test(readFileSync(f, 'utf8')));
      expect(offenders).toEqual([]);
    });
  }

  it('uppercase appears at most once, on the wordmark', () => {
    const offenders = files.filter((f) => /uppercase/.test(readFileSync(f, 'utf8')));
    expect(offenders.length).toBeLessThanOrEqual(1);
  });
});
```

- [ ] **Step 2: Run it**

Expected: PASS if Tasks 2–7 were complete. **Any failure names the exact file still carrying the class — fix those files before continuing.** Do not weaken the test; it is the spec's acceptance criterion.

- [ ] **Step 3: Lock the radius ladder**

In `frontend/tailwind.config.js`, add `borderRadius` at `theme` level — **not inside `extend`** — so it replaces Tailwind's defaults and the removed radii stop resolving:

```js
    theme: {
        borderRadius: {
            none: '0',
            sm: '4px',
            md: '8px',
            lg: '14px',
            full: '9999px',
        },
        extend: {
            // …colors, fontFamily, padding, margin, height as before
        },
    },
```

- [ ] **Step 4: Rebuild and check the bundle**

```bash
cd <worktree> && docker run --rm -v $PWD/frontend:/app -w /app node:18-alpine sh -c 'npm run build && npm run check:bundle'
```

Expected: PASS. Report the entry size against the 77 KB it was before this plan.

- [ ] **Step 5: Run the whole suite one final time**

Expected: all pass — the 33 pre-existing plus everything added here.

- [ ] **Step 6: Commit**

```bash
git add frontend/tailwind.config.js frontend/src/test/no-banned-classes.test.js
git commit -m "feat(frontend): lock the radius ladder and gate banned classes"
```

---

## Done when

- `no-banned-classes.test.js` passes: zero `font-black`, zero wide tracking, zero 10–11px text, zero removed radii, zero coloured shadows, zero gradient text, zero default-palette classes, at most one `uppercase`.
- The contrast gate passes, including caption-on-ground and white-on-accent.
- All pre-existing frontend tests still pass.
- `check:bundle` passes; the entry-size delta is recorded.
- `Hotspot/index.jsx` is under 1,000 lines with seven extracted panels.
- No element has moved: the diff contains no changed spacing, flex, grid or position class.

## Not in this plan

- Any layout change, element reposition or new page.
- The four rejected aesthetic directions (A–D on the design canvas). They stay as a record.
- Deploying. The frontend needs an image rebuild to reach production, and that is a separate, approved step.
- Pushing to GitHub — the remote still carries a plaintext PAT.
