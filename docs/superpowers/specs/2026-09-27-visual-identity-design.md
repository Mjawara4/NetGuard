# NetGuard Visual Identity — Design

**Date:** 2026-09-27
**Branch target:** a new branch off `perf/router-data-optimization` (currently 44 commits ahead of origin, unpushed)
**Status:** Draft

## The problem, measured

The frontend reads as a 2022 SaaS dashboard template. The cause is specific, not vague:

| Finding | Count | Why it matters |
|---|---|---|
| Uses of Tailwind's default `gray` scale | ~1,017 | The palette is the framework default, untouched. It contributes nothing to identity. |
| `blue-600` as the only real accent | 87 | Also the framework default. |
| `font-black` | 222 | When everything is heaviest weight, nothing is emphasised. |
| `uppercase` | 210 | Tracked-out caps labels are the single commonest generated-UI tell. |
| `text-[10px]` | 161 | Below comfortable reading at arm's length — and this app is used on a phone, outdoors, at a counter. A usability bug in a style costume. |
| Distinct radii in use (`lg`,`xl`,`2xl`,`3xl`,`full`) | 5 | No ladder; radius carries no meaning. |
| `shadow-blue` (coloured shadows) | 31 | Dated specific. |
| Gradient wordmark (`from-blue-600 to-indigo-600` + `bg-clip-text`) | 2 | The most dated single element in the app. |

**Diagnosis:** all of the app's personality is carried by loud typography over a palette that says nothing. The typography is the dated part.

## What this is NOT

Four full aesthetic directions were mocked up and reviewed (canvas: `NetGuard Design Directions`). Three failed an AI-slop audit on named tells — cream-plus-serif, near-black-plus-acid-accent, all-caps labels, monospace-as-label-styling, middle-dot meta strings, left-border accent boxes. The fourth was grounded in the business but drab.

**So this spec does not change the aesthetic. It refines the existing one.** No layout moves. No element repositions. The operator's muscle memory is preserved, and the work ships page by page with each step independently revertible.

## Decisions

These were delegated and are settled. They are not open questions.

### Neutrals — a temperature, not the default

Tailwind's `gray` is replaced by a custom scale shifted very slightly **green-cool** (hue ≈ 175°, chroma ≤ 0.012). Chosen over `slate` (reads blue/corporate), `stone` (goes muddy brown in dark mode, which this app needs for night monitoring) and `zinc` (dead neutral). Low chroma keeps it from looking tinted; the shift is felt, not seen.

```js
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
}
```

`ink-50` replaces `gray-50` as the page ground; `ink-900`/`950` are the dark-mode grounds. Deliberately not `#111` or `#0B0B0B`, which are the tell of a tinted near-black standing in for black.

### Accent — deep violet, one of them

`blue-600` is replaced by a single accent:

```js
signal: {
  300: '#BB86D4',   // dark-mode accent TEXT only — see note below
  400: '#A971C4',
  500: '#8F4FAF',
  600: '#7C3E9C',   // primary — buttons, active nav, focus rings
  700: '#653180',
}
```

`signal-300` was added during implementation, not designed up front. Browser
measurement found accent links on a card's `ink-800` fill at 3.65:1 in dark mode
— `signal-400` clears the page ground `ink-900` but not the cards that sit on
it. `#BB86D4` is the least-light shade clearing 4.5:1 on **both** dark grounds
(4.66 on `ink-800`, 5.94 on `ink-900`), chosen so it stays recognisably violet
rather than washing out to pale lavender.

It is **dark-mode-only**: 2.63:1 on `ink-50`, so it must never appear without a
`dark:` prefix. `signal-600` is its light-mode counterpart. The token test
enforces both a floor and a ceiling on it, the ceiling being what stops a later
"just make it lighter" edit from turning the accent pale.

Chosen because: it is not the framework default; it collides with **no** status semantic (unlike amber, which fights "warning", or teal, which fights "success"); it holds contrast on both `ink-50` and `ink-950`; and saturated violet is market-adjacent in West African telecom without imitating any operator's brand.

### Status colours — differentiated by lightness, not hue alone

Red/green alone fails for colour-blind users, and this app signals router up/down constantly. Each status keeps a distinct lightness and is always paired with a non-colour cue (shape, or the word).

```js
up:    '#2F7D62',   // lighter than `down`
down:  '#9A3A22',   // lighter, warmer
warn:  '#8A6114',
```

These three are the **only** semantic colours, and they serve every use — router up/down, alert severity, a destructive button, a success badge. The app currently reaches for `emerald-600` (35 uses) and `red-*` (56 uses) somewhat interchangeably for "good" and "bad"; both collapse into this trio. There is no separate "danger" or "success" palette, because a second red would drift from the first.

Destructive actions are distinguished by **weight and position**, not by a unique colour: a delete button is `down` coloured, and is never the primary action in its group.

### Radius ladder — three steps, tied to element size

| Token | Value | Applies to |
|---|---|---|
| `rounded-sm` | 4px | inputs, badges, small controls, table cells |
| `rounded-md` | 8px | cards, panels, buttons |
| `rounded-lg` | 14px | modals, sheets, the largest surfaces |

`rounded-2xl`, `3xl` and `xl` are removed. `rounded-full` survives **only** for genuinely circular things (status dots, avatars).

### Type policy

Weights: `400` body, `500` emphasis, `600` headings, `700` numerals and page titles. **`font-black` (900) is removed entirely** — 222 uses collapse to zero.

Labels: sentence case, **12px floor** (`text-xs`), normal tracking.

`uppercase` is removed everywhere with exactly one permitted exception: the `NetGuard` wordmark in the app shell, if the final wordmark treatment wants it. `tracking-widest` is removed with no exceptions. "At most two places" would be unenforceable — the rule is zero, plus one named exception, so a grep is a pass/fail test.

Numerals: tabular figures, one size step up from their label, weight 700. Numbers are this app's content — counts, codes, latency — and should be the thing the eye lands on.

**One webfont, for headings and numerals only: Instrument Sans.** Body text stays `system-ui`. Chosen for its figures and for not being overexposed; explicitly not Inter, Roboto, Arial or Fraunces.

**Cost, stated plainly:** a latin-subset variable woff2 is roughly 20–30 KB. The entry bundle is currently 77 KB after the code-splitting work, so this is a real regression on a number that was just fought for. It is worth it — system-ui is a large part of why the app reads as generic — but it must be `preload`ed and subset, and if measurement shows it pushing past ~110 KB the spec falls back to system-ui everywhere and takes the identity from palette and restraint alone.

### Three ideas carried over from the mockups

Not looks — information design:

1. **Domain language.** "Books" not "batches". "Print 500 vouchers" not "Generate". "Reprint" on history. Free to do, and it makes the app sound like the business it serves.
2. **A colour band per voucher profile.** The way denominations are coded on prepaid cards, so `default` / `day-pass` / `week` are told apart without reading. This is data, not decoration — the band colour comes from the profile, and is the same everywhere that profile appears.
3. **Monospace on voucher codes, IPs and durations only.** Read character-by-character, so the face encodes something. Never on labels, which was the specific tell in the rejected mockups.

## Architecture

### Tokens live in one place

`frontend/tailwind.config.js` gains `colors.ink`, `colors.signal`, the status trio, the radius overrides and `fontFamily.display`. Nothing else may define a colour. A page that needs a shade it cannot find is a signal the ladder is wrong, not licence to inline a hex.

### The UI kit is the enforcement point

`frontend/src/components/ui/` (Button, Card, PageHeader, StatCard, Badge, Input, Skeleton) is rebuilt against the tokens first. Pages then migrate by *deleting* inline styling and using the kit — so the migration reduces code rather than adding it. `StatCard` in particular absorbs the numeral treatment, which removes the `font-black`/`text-[10px]` pairing from every page that uses it.

### Migration order

Cheapest-to-verify first, highest-risk last:

1. Tokens + UI kit (no page changes; existing pages keep working because the kit's API is unchanged)
2. Login, Signup — smallest surface, and where the `htmlFor`/`id` accessibility fix lands
3. Dashboard, Sites, Reports, NetworkMap — straightforward pages
4. Devices, Settings, AdminDashboard
5. Hotspot — largest and last

### The Hotspot file

`frontend/src/pages/Hotspot/index.jsx` is **2,178 lines**, ten times the next-largest page, and has grown across three recent plans. Migrating its styling means touching most of it.

A *targeted* extraction is in scope: each tab panel (Users, Active, Profiles, Generator, Books, Logs, Reports) moves to its own file under `pages/Hotspot/panels/`, with `index.jsx` keeping state, data fetching and tab routing. That is a mechanical move, not a rearchitecture. A full rewrite of its data flow is explicitly out of scope.

## Verification

- **Counts as the acceptance test.** `font-black` → 0. `uppercase` → ≤ 2. `text-[10px]` → 0. `rounded-2xl`/`3xl` → 0. `shadow-blue` → 0. Gradient wordmark → 0. Raw `gray-*` → 0. Raw `blue-*` → 0. These are greppable and belong in the plan as per-task checks.
- **Frontend tests must not regress.** Baseline is 24 passing (vitest). Route and shell tests cover that pages still render.
- **Bundle budget.** `npm run check:bundle` must still pass its 350 KB entry budget; record the delta the webfont adds.
- **Contrast.** Every token pair used for text meets 4.5:1 (3:1 at 24px+). The `ink-400`-on-`ink-50` caption combination is the one most likely to fail and must be checked explicitly.
- **Dark mode.** Every page keeps working in both themes; the new neutrals must be checked in dark mode specifically, since that is where a mis-toned scale shows.

## Out of scope

- Any layout change, element reposition or new page.
- The aesthetic directions A–D. They stay on the canvas as a record of what was rejected and why.
- The derived cache index that would take hotspot reads under 50 ms, and `/users/search` still calling the router — both tracked elsewhere.
- Pushing anything to GitHub. The remote still carries a plaintext PAT and that decision is the operator's.
