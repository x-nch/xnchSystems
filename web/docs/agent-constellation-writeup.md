# Agent Constellation — differentiation writeup

**Route:** `/constellation` · **Status:** static-topology prototype · **Deck:** interview talking points

---

## 1. The problem with "hub and spoke" AI product pages

Most agent/AI landing pages use the same visual grammar:

- A **perfectly symmetric radial diagram**: product logo dead-center, feature
  bubbles at equal radius, every node the same size and distance from the hub.
- **Nodes are decorative or navigational**: hover shows a tooltip, click routes
  to a feature page or opens a marketing modal. The diagram communicates
  "we have components," not "here's how the system actually behaves."
- **The center is the brand mark**, so the diagram reads as a logo treatment,
  not as an architecture claim.

The message that lands is: *"everything points at us."* The message that should
land for a serious system is: *"everything has a job, and one node decides."*

## 2. How this page breaks that pattern

### 2a. Asymmetric layout — it reads as a field, not a diagram

The core (Nexi) sits **off-center** at roughly the golden-ratio point of the
stage. Specialist nodes are placed at **deliberately irregular radii and
angles** — Memory is near the left edge, the router low-center, inference
bottom-right, the HITL gate large and top-right. There is no shared orbit and
no equal spacing. Nothing about the composition says "template."

Why it matters: an asymmetric field forces the eye to *explore* instead of
instantly pattern-matching to every other hub-and-spoke hero. It also makes a
subtle architectural point — subsystems are not satellites orbiting a logo;
they are a scattered constellation with unequal importance, and the HITL gate
is the biggest object in it.

### 2b. Interaction is "interrogate," not "navigate"

- Clicking a node **focuses it**: the selected orb enlarges and pulses, its
  orbital link lights up and animates, and every other node dims. Clicking the
  core collapses the whole field into a system-wide summary with readouts.
- The detail panel is **anchored in the stage**, not a modal — the selected
  node and its explanation share the same viewport, so the relationship
  between "what I clicked" and "what I'm reading" is never lost.
- Keyboard: arrow keys move focus across the constellation, Enter selects,
  Escape returns to the whole-system view.

The difference from a typical teaser: competitors *present* their stack; this
page asks you to *interrogate* one subsystem at a time, and the interaction
itself is the argument — when you select one thing, everything else visibly
stands down.

### 2c. The HITL gate is the visual protagonist

The gate is the **largest node** (1.28× weight), uses a **distinct square
"gate" silhouette** against the circular orbs, has its own blinking beacon
ring, and is the only node rendered in a blocked/awaiting state. It sits at
the top-right — the "edge" of the composition — which visually says *this is
the boundary between the system and the human*. Its copy in the narrative
section carries the strongest claim:

> *"The human isn't a safety feature. It's a stage."*

This is the differentiation that matters commercially: most products market
HITL as a compliance badge. This page presents it as the load-bearing
architectural decision.

### 2d. Copy voice — Nexi's, not marketing's

The narrative reads in first-person-singular system voice: direct,
non-sycophantic, zero buzzwords ("decision pipeline," "block by default,"
"100% traced," "if it isn't traced, it didn't happen"). No "revolutionary,"
no "empower," no exclamation marks. The page is written the way the system
would describe itself to an operator — which is the exact tone that
distinguishes a real control plane from a demo.

## 3. Component plan

```
src/app/constellation/
  layout.tsx            # Inter font, metadata, imports scoped CSS
  page.tsx              # renders <ConstellationLanding />
  constellation.css     # chartreuse tokens + orb/ring/link/reveal keyframes

src/components/constellation/
  constellation-landing.tsx   # page composition + selection state
  constellation-stage.tsx     # asymmetric field, curved SVG links, focus logic,
                              #   ResizeObserver sizing, keyboard nav
  core-orb.tsx                # Nexi core: breathing halo + StatusPulse rings
  agent-orb.tsx               # specialist node (gate variant = square beacon)
  detail-panel.tsx            # agent blurb/detail OR core system summary
  narrative-sections.tsx      # scroll-driven reveal below the stage

src/lib/constellation/
  data.ts               # static topology + copy (swap for live health later)
```

**Data boundary:** every node's position, status, blurb, and the narrative are
plain data in `data.ts`. The interaction layer reads nothing but that file —
wiring it to real subsystem health later is a data-replacement task, not a
component rewrite.

## 4. Why this is defensible in an interview

- **"How is this different from every AI teaser page?"** — No symmetric hub,
  no logo-as-center, no navigate-on-click. The layout is asymmetric, the
  interaction is focus/inspect rather than link/modal, and the largest visual
  object is the human gate — not the model, not the logo.
- **"Why is HITL the hero?"** — Because it's the one thing competitors can't
  copy by adding a feature. A gate that *blocks by default* and requires an
  explicit operator answer is an architectural posture; the page makes that
  the first thing you see, at 1.28× the size of everything else.
- **"Is it just static?"** — The prototype is, intentionally. The component
  boundary treats topology as data, so live status, metrics, and gate state
  can be dropped in without touching the interaction layer.
- **"Why chartreuse on near-black?"** — One accent, no gradient rainbow.
  Restraint reads as engineering confidence; the same reason the copy has no
  hype.
