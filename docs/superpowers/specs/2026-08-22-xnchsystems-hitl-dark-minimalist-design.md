# xnchSystems — Dark Minimalist Chartreuse Design Spec
### Reconciliation UI: HITL Gate as Primary, Fixing Decorative State & Accessibility

**Date:** 2026-08-22
**Status:** Approved direction — dark minimalist chartreuse (replaces Apex palette)
**Decision resolved:** Background near-black + #C8FF00 single accent + Space Grotesk / Inter. No orb-and-node-graph, no cyan/navy HUD. Rationale in §4.
**Scope:** Approval Queue (new home screen), Status/Presence redesign, tokens, reduced-motion & contrast fixes, Firefox baseline
**Affects:** `web/src/app/globals.css:1`, `web/src/app/layout.tsx:7`, `web/src/components/network/*`, `web/src/components/presence/particle-humanoid.tsx`, `web/src/components/layout/connection-status.tsx`, `web/src/components/ui/*`

---

## 0. Context — What the audit found (verified against shipped code)

| # | Finding | Evidence |
|---|---|---|
| 1 | HITL gate has **zero** UI surface | No route, component, or store for approvals. `web/src/components/layout/sidebar.tsx:26` NAV has Network/Chat/Memory/Graph/Tools/System/Presence — no Approvals. Scheduler/goals invisible. |
| 2 | Status indicators are decorative | `web/src/components/network/core-node.tsx:30` `.orb-halo` + `web/src/components/network/core-particles.tsx:21` animate identically for `ok`/`degraded`/`offline` (only border + dot change). `web/src/components/network/waveform.tsx:35` canvas animates regardless of `gatewayOk`. `"tracking subsystem online"` is not present but pattern repeats: `web/src/components/layout/connection-status.tsx:30` labelText is correct but dot is the *only* state cue at 8px; `agent-node.tsx:39` offline = `opacity-45 saturate-50` — same animation at lower opacity, not a distinct dead state. |
| 3 | Zero `prefers-reduced-motion` handling | Infinite animations: `globals.css:167` `x-orb-halo` 4s, `x-node-drift` 3.2s, `x-scanline` 8s, `x-node-active` 2s, `x-cursor-blink`, `x-pulse-dot`, plus `core-particles.tsx:33` rAF 48 particles and `particle-humanoid.tsx:107` 1400 particles. No `@media (prefers-reduced-motion)` anywhere (grepped). |
| 4 | State borders fail WCAG AA non-text contrast | `globals.css:240` `hud-panel` uses `rgba(34,211,238,0.12)` border; `agent-node.tsx:46` `border-cyan-300/20` (= rgba 0.20) and `glow-border` `rgba(34,211,238,0.22)`. Blended over `--background: #020617` these yield effective contrasts **1.33–1.82:1** (measured) — well under 3:1. Offline `border-border/40` (~0.16) also fails. Any alpha <0.40 fails for cyan on near-black. |
| 5 | Firefox is primary browser | Owner uses Firefox exclusively. Current CSS relies on `backdrop-filter` (supported) but no Chromium-only features today — must keep it that way. No `anchor()`, no `view-transition`, no `::-webkit-scrollbar`–only patterns without fallback. |

---

## 1. Design Token Spec

### 1.1 Principles

- **Near-black, not pure black.** Pure #000 leaves no headroom for cards/scrim — surfaces become invisible. Near-black `#0C0F14` gives ~1.1–1.2:1 steps to surfaces while keeping total darkness.
- **Chartreuse means `needs-attention`.** It is not a brand wash. Used for: pending HITL count, attention borders, primary action. Healthy/done states use separate, muted greens; offline uses neutral grey — never chartreuse.
- **State is never communicated by opacity alone.** Every state has a distinct hue + icon + border + label. Borders that carry meaning are solid hex at ≥3:1 vs background (computed, not guessed).
- **Type: Space Grotesk (display) + Inter (body).** JetBrains Mono retained only for code/ids.

### 1.2 Core palette (exact values — do not drift)

| Token | Value | Usage | Contrast vs `--bg-base` |
|---|---|---|---|
| `--bg-base` | `#0C0F14` | page background, `themeColor` | — |
| `--bg-surface` | `#141A1F` | cards, panels, sidebar | 1.09:1 vs base (deliberately subtle; edge defined by border) |
| `--bg-raised` | `#1C242C` | hover, popover, dropdown | 1.22:1 vs base |
| `--bg-scrim` | `rgba(12,15,20,0.82)` | backdrop behind modals | — |
| `--text-primary` | `#F2F4F7` | headings, primary text | **17.4:1** |
| `--text-secondary` | `#A8B3CF` | body, secondary | **9.15:1** |
| `--text-muted` | `#7A869F` | metadata, timestamps | **5.24:1** |
| `--text-faint` | `#5A6780` | disabled, placeholder | **3.37:1** (minimum for large text) |
| `--border-subtle` | `rgba(242,244,247,0.08)` | non-state dividers | decorative, no 3:1 requirement |
| `--border-strong` | `rgba(242,244,247,0.14)` | card outer edge (non-state) | decorative |
| `--accent` | `#C8FF00` | chartreuse — attention only | **16.2:1** vs base (when solid) |
| `--accent-ink` | `#0C0F14` | text on accent buttons | 16.2:1 vs accent |
| `--accent-subtle` | `rgba(200,255,0,0.10)` | attention row tint, NOT a border | — |
| `--accent-ring` | `#C8FF00` | focus ring when attention context | — |

### 1.3 State palette (all borders are **solid hex**, pass 3:1 vs `--bg-base` at 1px)

| State | Token | Value | Contrast | Icon | When to use |
|---|---|---|---|---|---|
| **Needs attention** | `--state-attention` / `border-attention` | `#7A9E0A` (border) / `#C8FF00` (icon/solid) | **6.14:1** (border) | `◉` or `AlertTriangle` in `#C8FF00` | pending HITL, blocked goal, requires human |
| **Healthy / online** | `--state-healthy` | `#2E8B6A` border / `#3DD598` icon | **4.59:1** | `●` in `#3DD598` | gateway ok, agent idle/ok |
| **Degraded / warning** | `--state-degraded` | `#9A7B1A` border / `#FFC857` icon | **4.77:1** | `▲` in `#FFC857` | degraded health, retrying |
| **Offline / dead** | `--state-offline` | `#5A6780` border / `#7A869F` icon | **3.37:1** | `■` or `Minus` in `#7A869F` | disconnected, stopped, no heartbeat |
| **Destructive** | `--state-destructive` | `#B84A4A` border / `#FF6B6B` icon | **3.3:1** after tuning | `✕` | failed action, error |

> **Why solid hex, not alpha:** Measured in audit — `rgba(34,211,238,0.12)` blended → #142… @ 1.33:1. Even chartreuse at 0.30 → 2.40:1. Minimum passing alpha for chartreuse is **0.40** (3.37:1). Other hues need 0.50–0.60. Solid tokens eliminate the guesswork and are easier to audit in Firefox DevTools.

For chartreuse attention rows, use: `border: 1px solid #7A9E0A` + `background: rgba(200,255,0,0.06)` + left accent bar `4px solid #C8FF00`. The left bar is 4px solid, so 16:1 — unambiguous. Tints (0.06) are decoration; the border + bar carry the 3:1 guarantee.

### 1.4 Type scale

| Level | Font | Size / Line | Weight | Usage |
|---|---|---|---|---|
| Display | Space Grotesk | 24/28 | 600 | screen titles ("Approvals") |
| H2 | Space Grotesk | 16/22 | 600 | section headers |
| H3 | Space Grotesk | 13/18 | 600 | card titles |
| Body | Inter | 13/20 | 400 | primary reading |
| Body sm | Inter | 12/18 | 400 | list rows, detail |
| Meta | Inter | 11/16 | 500 | timestamps, counts, uppercase labels (`tracking-widest` retained but at 10–11px, not 9px) |
| Mono | JetBrains Mono | 11/16 | 400 | ids, `system_state_version`, policy hashes |

Minimum body is **11px** (up from 9–10px in `network-hud.tsx:52`). The shipped 9–10px mono labels fail legibility and are chartreuse-tint dependent.

### 1.5 Spacing & radii

- Base unit 4px. Scale: 4, 8, 12, 16, 24, 32.
- Card radius: `12px` (outer), `8px` (inner blocks). No pill badges for state — rectangles with `6px` radius.
- Focus ring: `0 0 0 2px var(--bg-base), 0 0 0 4px var(--accent)` for attention context; otherwise `var(--accent)` at 2px.

### 1.6 CSS mapping (patch for `web/src/app/globals.css:3`)

```css
:root {
  --background: #0C0F14;          /* was #020617 */
  --foreground: #F2F4F7;          /* was #e2e8f0 */
  --card: #141A1F;                 /* was #030712 */
  --card-foreground: #F2F4F7;
  --muted: #1C242C;
  --muted-foreground: #7A869F;    /* was #8b98b3 */
  --border: rgba(242,244,247,0.10);
  --input: #1C242C;
  --ring: #C8FF00;                /* was #22d3ee */
  --accent: #C8FF00;              /* was #22d3ee */
  --accent-foreground: #0C0F14;   /* was #03131a */
  --accent-subtle: rgba(200,255,0,0.10);
  --success: #3DD598;             /* was #34d399 — keep but standardize */
  --warning: #FFC857;             /* was #fbbf24 */
  --destructive: #FF6B6B;         /* was #f87171 — passes at solid */
  --state-attention: #7A9E0A;
  --state-healthy: #2E8B6A;
  --state-degraded: #9A7B1A;
  --state-offline: #5A6780;
}
```

Delete from `globals.css`: `glow-border`, `glow-border-gold`, `glow-text`, `hud-grid`, `vignette`, `orb-halo`, `node-drift`, `scanline-overlay`, and the two `radial-gradient` body washes (`globals.css:68`). Replace with a single flat `background: var(--background)` — chartreuse is applied only at component level per 1.3.

---

## 2. Approval Queue / HITL Gate — New Primary Screen

### 2.1 Positioning

- Route: `/` becomes the approval queue (not `/network`). `Network` moves to `/network` secondary. Sidebar `web/src/components/layout/sidebar.tsx:27` reorders: **Approvals (1)** at top, with live count badge in chartreuse when >0, then Network, Chat, etc.
- Empty queue shows calm state: `"No pending approvals — system is idle or autonomous within policy."` with healthy indicator. No decorative animation in empty state.
- Queue is polling/backed by `GET /api/approvals?status=pending` (to be implemented in `xnch` control plane) and falls back to local store if offline — offline queue shows counts but actions disabled (see 2.4).

### 2.2 List view (screen 1)

```
┌─ Top bar ──────────────────────────────────────────────────────┐
│ Approvals  ● 4 pending · 1 overdue    [Filter: All ▾] [⌘K]    │
├──────────────────────────────────────────────────────────────┤
│ ┌─ Row (needs attention — chartreuse) ──────────────────────┐ │
│ │ ■ 4px left bar #C8FF00  │  EXECUTE TOOL  ·  agent:research  │ │
│ │ [◉] Propose: write file  `reports/q3.md`                     │ │
│ │     Goal: "Draft Q3 summary"  ·  Policy: allow with approval │ │
│ │     Waiting 12m · Overdue in 18m · id: req_8f31             │ │
│ │     [Approve] [Reject]  [View detail →]                    │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌─ Row (needs attention) ───────────────────────────────────┐ │
│ │ Schedule   ·  cron: weekly digest  · Waiting 43m            │ │
│ │ Propose: send email to team@                                │ │
│ │ [Approve] [Reject] [View detail →]                         │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌─ Row (degraded — amber, long-waiting) ───────────────────┐ │
│ │ Waiting 3h 12m · auto-expires in 47m                        │ │
│ └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

Spec:

- Flat list, newest overdue at top, then by `waiting` desc. No cards with glow; rows are `bg-surface` with `1px solid var(--state-attention)` when pending, left 4px accent bar for attention. Degraded (waiting >2h) uses `var(--state-degraded)` border instead — still 4.77:1.
- Each row contains (all text, no icon-only meaning):
  1. **What action is proposed** — verb + target: `"Write file reports/q3.md"` / `"Execute tool: web_search"` / `"Send email to …"`. Not "tool_call_id".
  2. **Which agent/goal it came from** — `agent:research` + `goal:"Draft Q3 summary"` (both as plain text pills with `border-strong`, not color-only).
  3. **How long pending** — `"Waiting 12m"` (updates each minute) + `"Overdue in 18m"` or `"Overdue by 3m"` when past deadline. Overdue rows gain `border-attention` even if previously degraded.
  4. **Controls** — `[Approve]` (solid chartreuse, `text-accent-ink`), `[Reject]` (outline `border-strong`), and `[View detail →]` (ghost). All are `<button>` with visible labels; not icon-only.
- Keyboard: `j/k` to move, `a` approve, `r` reject, `Enter` open detail, `?` help. Focus ring is chartreuse double-ring per 1.5.

### 2.3 Detail / decision view (screen 2)

Opens as a panel (not a modal) on the same route: `/?selected=req_8f31` → right pane on desktop, full-screen stack on mobile.

```
┌─ Detail pane ─────────────────────────────────────────────┐
│ ← Back to queue                         Waiting 12m · req_8f31│
│ Propose to write file                                         │
│ ┌─ Proposed action (code block, JetBrains Mono) ─────────┐ │
│ │ path: reports/q3.md                                      │ │
│ │ bytes: 4.2k · diff: +42 −3                               │ │
│ │ ─ preview (first 40 lines, scrollable) ─                │ │
│ └────────────────────────────────────────────────────────┘ │
│ Provenance                                                  │
│ • Agent: research (model: ornith)  • Goal: goal_9c2…       │
│ • Policy: `default` v12  • Trigger: scheduler weekly_digest │
│ • Requested: 2026-08-22 14:12 UTC  • Expires: 15:12 UTC     │
│ Risks / policy notes                                        │
│ • Writes to git-tracked path. No secrets detected.          │
│ Decision                                                    │
│ [Approve and execute]  [Reject]  [Reject with note…]        │
│ Reject note (optional, shown on reject): [___________]      │
│ After decision: row animates out; list reflows. Toast with Undo (8s). │
└────────────────────────────────────────────────────────────┘
```

Spec:

- **No destructive default.** Neither button is focused by default; user must Tab or click. `Enter` in list does not approve.
- Approve is `variant: attention` (chartreuse solid). Reject is `outline`. "Reject with note" expands a textarea.
- Shows **full provenance**: agent id, `goal_id`, `policy_version`, `scheduler` trigger if any, `expires_at` — all as text, not hidden in tooltip.
- Audit: on approve/reject, emit `emit_event` (existing pattern `xnch/utils/audit.py`) and update row to `decided` with strikethrough then removal after 800ms (or instant under reduced-motion).

### 2.4 States for the queue itself

| Queue state | Visual |
|---|---|
| **Checking** (`isPending`) | Top bar shows `"Checking for approvals…"` + muted spinner (12px, `border-muted` spinner, not chartreuse). List is skeleton rows with `bg-surface` (no glow). |
| **Healthy, empty** | `"No pending approvals"` + healthy indicator `● #3DD598` + `border-healthy` on the empty panel. |
| **Has pending** | Count badge in chartreuse (`bg-accent text-accent-ink`) on sidebar + top bar `"4 pending · 1 overdue"` where `overdue` is chartreuse text. |
| **Offline** | Banner: `"Gateway offline — approvals cannot be executed. Showing 2 cached pending."` Banner is `border-offline #5A6780` + `bg-raised`, not red, with `■` offline icon. Approve buttons disabled with `disabled:opacity-50`. No fake live count. |
| **Degraded** | Banner: `"Gateway degraded — actions may be slow."` in `border-degraded #9A7B1A`. |

### 2.5 Data contract (for `xnch`/`nexi` integration)

Minimal shape the UI expects (Pydantic-style):

```ts
type HitlRequest = {
  id: string;               // req_*
  status: "pending"|"approved"|"rejected"|"expired";
  created_at: string;       // ISO
  expires_at: string | null;
  agent_id: string;
  goal_id: string | null;
  trigger: { kind: "chat"|"scheduler"|"policy", id: string } | null;
  action: { kind: "write_file"|"exec_tool"|"send_email"|..., summary: string, preview?: string, args: unknown };
  policy_version: string;
};
```

If `xnch` endpoint not yet available, UI reads from React Query + local Zustand queue seeded from `POST /api/gateway/hitl` (mockable). Offline banner logic in `web/src/components/layout/connection-status.tsx:8` is reused — `useConnectionState()` drives queue disabling.

---

## 3. Redesigned Status / Presence System

Replaces/fixes `AgentOrb`/`CoreNode`/`CoreParticles`/`Waveform`/`StatusPulse`.

### 3.1 Design intent

- If it's on screen, it means something a human can act on. No ambient particle field.
- Every indicator has **3 explicit visual states** — online / degraded / offline — not just "on".
- Legible at rest (no motion required to understand state).

### 3.2 Gateway / system presence (replaces `CoreNode` + `Waveform`)

Component: `StatusBeacon` (new, ~72px row, not an orb).

| State | Icon (16px) | Border | Label | Animation |
|---|---|---|---|---|
| **Online** | `●` in `#3DD598` (solid dot, 8px) | `1px solid #2E8B6A` (4.59:1) on `bg-surface` card | `"Gateway online"` + version/hash | Subtle 1.5s breathe on dot only (opacity 1→0.7). Under `prefers-reduced-motion`, dot is static. |
| **Degraded** | `▲` in `#FFC857` (tri, 14px) | `1px solid #9A7B1A` (4.77:1) | `"Gateway degraded"` + reason | No motion; tri is static. If motion allowed, a single 300ms nudge on transition only. |
| **Offline** | `■` in `#7A869F` (square, 10px) with diagonal strike | `1px solid #5A6780` (3.37:1) + `bg-raised` with `repeating-linear` 45° muted stripe (2px) | `"Gateway offline"` + `"Last seen 3m ago"` | **No animation at all.** Card is desaturated; stripe is static. Under reduced-motion also static (no difference — this is the fallback). |

Key difference from `core-node.tsx:30` `orb-halo` + `core-particles.tsx:21` infinite rAF: the beacon **fails visibly**. Offline is not "same orb at lower opacity" — it's a different shape, border, and label. The existing `useConnectionState()` (`connection-status.tsx:8`) is retained but its rendering is replaced per above.

The `Waveform` canvas (`waveform.tsx:35`) is deleted. Its replacement is a 24px sparkline only when online and data exists; otherwise a text readout `"No telemetry"` — never a live oscilloscope when disconnected.

### 3.3 Agent / node presence (replaces `AgentNode`)

Component: `AgentRow` (list row, not a floating card).

- Layout: leading dot/icon (state color) + name + role + last-active time; actions are text buttons. No `node-drift` (`globals.css:182`), no `glow-border`.
- Offline is not `opacity-45` (`agent-node.tsx:39`) — it's a distinct row with offline border + muted text + explicit `"Offline"` pill in `border-offline`. The trail of `Handle` (React Flow) remains but edges to offline nodes are dashed `stroke: #5A6780`.

### 3.4 Particle humanoid (`particle-humanoid.tsx:56`)

- **Delete from production routes.** It is the ~1400-particle rAF loop that accounts for most motion and fails the "if it's on screen it should mean something" rule — the humanoid silhouette carries no backend state.
- If a presence illustration is desired for `/presence`, replace with a static SVG silhouette (2.1kB) with no rAF, or a placeholder chart of real sessions. No canvas loop.

### 3.5 Reduced-motion contract (addresses finding #3)

All animations obey:

```css
@media (prefers-reduced-motion: reduce) {
  .orb-halo, .node-drift, .scanline-overlay::after,
  .streaming-dot, .streaming-cursor,
  .node-active, .presence-enter, .crossfade-in {
    animation: none !important;
  }
  canvas[data-motion="decorative"] { display: none; }
  .presence-enter { opacity: 1; filter: none; transform: none; }
}
```

And in JS, every `requestAnimationFrame` loop must check:

```ts
const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (prefersReduced) return; // render static fallback instead of rAF
```

Fallbacks:
- `CoreParticles` → static concentric ring (`border: 1px solid #2E8B6A` when online; `#5A6780` when offline).
- `Waveform` → `—` or sparkline image (no canvas).
- `streaming-dot` → single static dot when reduced-motion.
- `x-cursor-blink` → solid block cursor (no blink).

Firefox: `matchMedia("(prefers-reduced-motion: reduce)")` is baseline and supported in Firefox since 63. No Chromium-only `prefers-reduced-motion` polyfill needed.

### 3.6 Contrast compliance (addresses finding #4)

Measured table (vs `--bg-base #0C0F14`) — every state border is solid hex:

- Attention `#7A9E0A` → **6.14:1** PASS
- Healthy `#2E8B6A` → **4.59:1** PASS
- Degraded `#9A7B1A` → **4.77:1** PASS
- Offline `#5A6780` → **3.37:1** PASS

Tints like `rgba(200,255,0,0.12)` blended → #242E13 @ **1.33:1** FAIL — therefore tints are never used for borders. Only for subtle row backgrounds where the border already carries the 3:1 guarantee.

Note for audit: cards also meet **focus visible** 3:1 via double-ring (`--bg-base` + `--accent`) — chartreuse ring on near-black is 16.2:1, well above 3:1.

---

## 4. Rationale — How This Differentiates from an Orb-and-Node HUD

**The HUD says: "Watch the magic." This says: "Decide."**

| Signal | Orb-and-node HUD (Reznikov / shipped `globals.css:4` Apex) | Dark minimalist chartreuse (this spec) |
|---|---|---|
| **Visual metaphor** | Navy (#020617) command center, cyan glow, gold accents, halos, particle fields, scanlines | Near-black flat surfaces, single chartreuse functional accent, typographic hierarchy |
| **Motion** | Halo breathes, nodes drift, waveform oscillates, particles orbit — all regardless of backend | Motion only when it encodes state (dot breathe when online; none when offline). Static, legible at rest. |
| **State legibility** | Online vs offline differ only in opacity (`opacity-45` vs `glow-border`). Animation continues when dead. | Offline is a different shape + border + label + stripe. Dead looks dead. |
| **Operator model** | System is opaque, autonomous, cinematic — human watches | System is patently waiting for human — queue count is the largest type on screen, Approve/Reject are the largest buttons |
| **Color semantics** | Cyan everywhere; gold for active — decorative | Chartreuse only for `needs-attention`; healthy/degraded/offline each have their own hue. Color = meaning. |
| **Accessibility** | 9px labels, low-alpha borders at 1.2–1.8:1, no reduced-motion | 11–13px minima, solid borders ≥3.37:1, full `prefers-reduced-motion` fallbacks |
| **Firefox** | No explicit issue but `glow-*` shadows are expensive + non-essential | No Chromium-only CSS; all features baseline (backdrop-blur is advisory, not load-bearing) |

The choice is deliberately calmer because the product claim is calmer: **"you can see what it's doing and approve or reject every consequential action."** A calm surface makes the rare chartreuse interruption — the pending approval — impossible to miss. An orb HUD makes everything glow, so nothing is urgent.

---

## 5. Firefox & Baseline Compliance

- No `anchor-positioning`, no `view-transitions`, no `scrollbar-*` that requires `-webkit-` only. Keep `scrollbar-width: thin` (`globals.css:79`) + `scrollbar-color` (Firefox-native) — already correct; retain.
- No `backdrop-filter` required for legibility — it stays as progressive enhancement on `bg-surface/80`; text contrast passes without it.
- All colors are hex/rgba; no `color-mix()` or `oklch()` that would shift in Firefox.
- `matchMedia("(prefers-reduced-motion: reduce)")` is Firefox-supported.

---

## 6. Implementation Checklist

1. **Tokens** — Patch `web/src/app/globals.css:3` per 1.6; delete Apex utilities; set `web/src/app/layout.tsx:25` `themeColor` to `#0C0F14` and swap `JetBrains_Mono` weight for `Inter`.
2. **Route ` /` → approvals** — Create `web/src/app/approvals/` (or repurpose `/`), move `NetworkView` to `/network`. Update `sidebar.tsx:26` NAV order + badge count.
3. **Queue components** — `components/approvals/approval-queue.tsx`, `approval-row.tsx`, `approval-detail.tsx`, `use-approvals.ts` hook (React Query). Wire to `useConnectionState()` for offline disabling.
4. **Status components** — Replace `CoreNode`/`Waveform`/`CoreParticles` with `StatusBeacon`; replace `AgentNode` styling; delete `ParticleHumanoid` from prod.
5. **Motion** — Add `@media (prefers-reduced-motion)` block + JS guards on all rAF loops.
6. **A11y pass** — Run axe + Firefox high-contrast + `prefers-reduced-motion: reduce` emulated; verify all state borders in DevTools contrast checker ≥3:1.
7. **No new decorations** — Lint rule: no `*.particles.*`, `orb-`, `glow-`, or canvas rAF without `prefers-reduced-motion` guard and a linked state prop in code review.

---

## 7. Open Questions (not blocking implementation)

- Policy phrase for approval row: should it show raw `policy_version` hash or a human label ("Default v12")? Propose label + hash in tooltip.
- `expires_at` semantics: if null, row never degrades? Propose: null = no auto-expire, stays attention until decided.

---

*End of spec. Next step: implement tokens + queue route; status beacon in parallel.*
