# Marketing "Cybernetic Noise" Treatment — Design Tokens & Spec

**Date:** 2026-08-24
**Status:** Approved (user approved all defaults)
**Affects:** `web/src/app/(marketing)/**` (new), `web/src/styles/marketing.css` (new), `web/src/components/marketing/**` (new), `web/src/app/layout.tsx` (slimmed), operator pages **moved** into `web/src/app/(operator)/` with byte-identical rendering.

**Scope boundary (hard):** Operator surfaces — HITL approval queue, system-health, HITL activity, inference performance, workflow builder — remain on the dark-minimalist-chartreuse functional system. No noise, glitch, scanline, or chromatic effect may reach them. See §5 Isolation Mechanics.

---

## 1. Base identity (unchanged)

Layered on top of, never replacing:

| Token | Value | Role |
|---|---|---|
| `--background` | `#0C0F14` | near-black base |
| `--accent` / `--ring` | `#C8FF00` | chartreuse |
| `--foreground` | `#F2F4F7` | body text |
| `--muted-foreground` | `#7A869F` | secondary text |
| Display font | Space Grotesk | headlines |
| Body font | Inter | all body copy |
| Mono font | JetBrains Mono | terminal-flavor accents (labels, kickers, chrome) |

Marketing adds a **new namespaced token block** (`--mkt-*`) defined only in
`src/styles/marketing.css`, imported only by `(marketing)/layout.tsx`.

## 2. Noise / grain treatment

| Token | Value | Notes |
|---|---|---|
| `--mkt-noise-opacity` | `0.05` | ≤ 6% hard cap |
| `--mkt-noise-tile` | `180px 180px` | tiled SVG data-URI |
| `--mkt-grain-blend` | `overlay` | separate layer div, not `background-blend-mode` on large areas |
| Animation | **none** | grain is fully static by design (see Safety) |

Implementation: inline SVG `feTurbulence type="fractalNoise" baseFrequency="0.8"
numOctaves="2" stitchTiles="stitch"` → grayscale alpha via `feColorMatrix`,
encoded as a ~700-byte data-URI background-image on an `aria-hidden`
pseudo-element that sits **below** content (`z-index: 0`; content wrappers get
`position: relative; z-index: 1`). Grain never overlays text pixels.

## 3. Scanlines / CRT accents

| Token | Value |
|---|---|
| `--mkt-scanline-opacity` | `0.04` |
| `--mkt-scanline-period` | `3px` (1px line + 2px gap) |
| `--mkt-vignette-strength` | `0.5` alpha at edges, transparent to 55% center |
| `--mkt-sweep-duration` | `9s` linear infinite — **hero section only** |

- Static scanlines: `repeating-linear-gradient(180deg, rgba(255,255,255,.04) 0 1px, transparent 1px 3px)` — constant, non-flickering.
- Vignette: static radial gradient suggesting tube curvature; no barrel distortion transform.
- Scan sweep: one soft 20%-height gradient bar translating through the hero at low opacity — continuous smooth motion, no stepping/strobing. Under `prefers-reduced-motion`: sweep element is `display:none`; the static scanline texture remains (genuinely static equivalent).

## 4. Glitch-text trigger rules

Applies ONLY to display headings (hero `h1`, section `h2`) marked `.mkt-glitch`.
**Never on nav links, CTAs/buttons, form labels, or body copy** — those are
fully legible always, with zero transform/filter of any kind.

| Rule | Value |
|---|---|
| Trigger | `pointerenter` / `focus-visible` only. No ambient timers, no scroll triggers, no autoplay. |
| Duration | ≤ 280ms, single shot per enter; re-trigger requires pointer leave |
| Technique | 2 × `clip-path: inset()` slices + `translateX(±2px)` max. No brightness inversion, no filter flashes, no RGB channel separation brighter than the text itself. |
| Cooldown safety | CSS animation runs exactly once per class toggle |

Chromatic-aberration hover (`.mkt-chroma`, card titles/feature links):
hover/focus-visible applies dual `text-shadow` fringes (magenta/cyan, α≤0.35)
over 120ms ease-out; resting state is clean. Under reduced motion this is
replaced by a plain chartreuse color shift — a genuinely static equivalent.

Terminal typing (hero subhead): full sentence server-rendered in DOM and
exposed via `aria-label`; if (and only if) JS runs and reduced-motion is off,
text retypes once at 18–28ms/char with a chartreuse block caret (1.06s step
blink, mirroring the existing `streaming-cursor` pattern). Reduced motion →
static sentence, steady caret, forever.

## 5. Isolation mechanics (operator safety)

1. Route-group split: operator pages live under `(operator)/layout.tsx`
   (Providers + AppShell unchanged); marketing under `(marketing)/layout.tsx`.
   URLs are identical to before (`/` = approval queue).
2. `marketing.css` is imported in exactly one file: `(marketing)/layout.tsx`.
3. Every marketing class is prefixed `mkt-`. Grep gate: `src/components/{approvals,observability,network,layout,ui,...}` must contain zero `mkt-` references.
4. Marketing does **not** reuse `components/ui/*` primitives — it has its own forked CTA/link styles so neither side can leak into the other.
5. Verification: `git diff` shows no modifications inside operator component/lib files; post-split build route table confirms operator routes render identically (static prerender count unchanged).

## 6. Safety compliance map

| Constraint | Mechanism |
|---|---|
| 1. Photosensitivity (WCAG 2.3.1) | Zero temporal luminance variation anywhere: grain static, scanlines static, vignette static. Only motions are (a) one soft sweep bar at α=0.05 over ≥9s and (b) interaction-triggered glitch ≤280ms with no brightness/inversion steps. No flashing content exists at any layer. |
| 2. Vestibular / reduced motion | Every animated effect has a genuinely static equivalent implemented in the same media query block: sweep→hidden (static texture remains), glitch→disabled (resting heading), chroma→color shift, typing→instant full text + steady caret. No "reduced" versions. |
| 3. Contrast over texture | Text sits above noise layers (never composited through). Worst-case grain-composited backgrounds computed in `src/lib/marketing/contrast.test.ts` against AA thresholds for every text/background token pair used on marketing pages. |
| 4. Firefox-first | Techniques chosen for FF parity: feTurbulence (FF-native), repeating-linear-gradient, mix-blend-mode on small layers, basic clip-path shapes, text-shadow, prefers-reduced-motion (FF 63+). Explicitly banned: `filter:url(#svg)` on HTML elements, backdrop-filter stacks, paint worklets/Houdini, mask compositing. Smoke-tested in headless Firefox via Playwright. |
| 5. Performance | Zero rAF/canvas/particle loops in marketing code (only one setTimeout per glitch trigger + bounded typing loop). All textures are static tiled backgrounds (~700B inline). Budget: marketing first-load JS delta <20KB/route over shared baseline; build-time delta <10%; verified before/after in §Perf Note. |

## 7. Perf & verification methodology

Measured on the real toolchain (Next.js 16.3 Turbopack production build,
`next start`, curl + Node fetch byte counts) before and after implementation.
Firefox verification ran against real headless Firefox 153 via Playwright
(audit script: `scripts/firefox-noise-audit.mjs`; requires
`npm i -D playwright && npx playwright install firefox`).

## 8. Perf note — measured

| Metric | Before | After | Δ |
|---|---|---|---|
| Warm production build (wall) | 18.1s | 17.9s | ≈0 |
| Top-12 static chunks | 324/224/176/152/112/72… KB | byte-identical set | shared/operator bundles unchanged |
| `/` approval-queue route assets | baseline shared bundle | 856 KB served | ±0 (pure renames; chunk list identical) |
| New marketing routes (`/product` `/services` `/teaching` `/community`) | — | 652 KB served each, fully static prerender | ships ~200KB LESS than any operator route |
| Marketing-unique runtime JS | — | two small client components (`glitch-text`, `type-terminal`); zero rAF / canvas / setInterval loops | within <20KB/route budget |

Scroll-jank reasoning (structural, not profiled): every texture is a static
tiled background painted once into a layer — there is no per-frame work by
construction; the only continuous animation is the hero sweep bar
(transform-only on a single element with `will-change: transform`). The
`.next/dev` + `.next/cache` disk growth seen during iteration is local build
cache, not shipped payload.

### Firefox 153 audit results (8/8 PASS)

All four routes × {no-preference, reduce}:

- grain opacity renders at exactly 0.05; scanlines/vignette present; CTA is opaque `rgb(200,255,0)` with `rgb(12,15,20)` label.
- `no-preference`: sweep animating, caret blinking, glitch class applies on hover and self-clears ≤280ms.
- `reduce`: sweep `display:none` (static texture remains), caret animation `none` (steady block), glitch never activates, full sentence present in DOM in both modes.

The audit caught and fixed one real bug a code review would plausibly miss:
the RM override `.mkt-noise__sweep { display:none }` was out-ranked by the base
rule `.mkt-noise > span { display:block }` (specificity 0,1,1 vs 0,1,0), so the
sweep kept animating under reduced motion in Firefox despite the CSS shipping
correctly. Fixed with `.mkt-noise > .mkt-noise__sweep { display:none !important }`.

### Known pre-existing issue (out of scope, not modified)

`(operator)/agents/page.tsx:34` fails the `react-hooks/set-state-in-effect`
lint rule. The file is content-identical to its pre-move version (pure rename;
see git diff `-M` output); the error predates this work and was left untouched
per the operator scope boundary.

### Screenshots

Full-page Firefox screenshots for all eight route/mode combinations were
captured during the audit run for manual review.
