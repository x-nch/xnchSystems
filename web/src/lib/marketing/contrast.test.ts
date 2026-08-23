/**
 * Constraint verification for the cybernetic-noise treatment:
 * every text/background token pair used on marketing pages must meet WCAG AA
 * against the noise-composited worst-case background, not the bare surface.
 * See docs/superpowers/specs/2026-08-24-marketing-cybernetic-noise-design.md §6.
 */
import { describe, expect, it } from "vitest";
import {
  contrastRatio,
  hexToRgb,
  relLuminance,
  overlayBlend,
  worstCaseBackground,
} from "./contrast";

const BASE = "#0C0F14";
const CARD = "#141A1F";

// Marketing-scoped text colors (styles/marketing.css)
const FG = "#F2F4F7";
const MUTED = "#8B96AD";
const ACCENT = "#C8FF00";

describe("color math sanity", () => {
  it("pure black/white spans the full ratio", () => {
    expect(contrastRatio({ r: 0, g: 0, b: 0 }, { r: 1, g: 1, b: 1 })).toBeCloseTo(21, 1);
  });

  it("identical colors give ratio 1", () => {
    expect(contrastRatio(hexToRgb(BASE), hexToRgb(BASE))).toBeCloseTo(1, 5);
  });

  it("luminance of white is 1 and black is 0", () => {
    expect(relLuminance({ r: 1, g: 1, b: 1 })).toBeCloseTo(1, 5);
    expect(relLuminance({ r: 0, g: 0, b: 0 })).toBeCloseTo(0, 5);
  });

  it("overlay blend of white yields white at any backdrop", () => {
    const out = overlayBlend({ r: 0.6, g: 0.6, b: 0.6 }, { r: 1, g: 1, b: 1 });
    expect(out.r).toBeCloseTo(1, 5);
    const dark = overlayBlend({ r: 0.05, g: 0.06, b: 0.08 }, { r: 1, g: 1, b: 1 });
    expect(dark.b).toBeCloseTo(1, 5);
  });
});

describe("noise-composited backgrounds stay darker than AA requires", () => {
  const worstBase = worstCaseBackground(BASE);
  const worstCard = worstCaseBackground(CARD);

  it("compositing only brightens surfaces (grain/scanlines are white)", () => {
    for (const worst of [worstBase, worstCard]) {
      const plain = hexToRgb(worst === worstBase ? BASE : CARD);
      expect(worst.r).toBeGreaterThanOrEqual(plain.r);
      expect(worst.g).toBeGreaterThanOrEqual(plain.g);
      expect(worst.b).toBeGreaterThanOrEqual(plain.b);
      // …but not by much — treatment stays subtle (<10% channel lift)
      expect(worst.r - plain.r).toBeLessThan(0.1);
    }
  });

  it.each([
    ["body text on textured base", FG, worstBase, 4.5],
    ["muted text on textured base", MUTED, worstBase, 4.5],
    ["body text on textured card", FG, worstCard, 4.5],
    ["muted text on textured card", MUTED, worstCard, 4.5],
    ["accent headline on textured base", ACCENT, worstBase, 4.5],
    ["accent kicker on textured card", ACCENT, worstCard, 4.5],
  ])("%s meets WCAG AA", (_label, fgHex, bg, threshold) => {
    const ratio = contrastRatio(hexToRgb(fgHex), bg);
    expect(ratio).toBeGreaterThanOrEqual(threshold);
  });

  it("CTA label (near-black on chartreuse fill) meets AA", () => {
    // CTAs render opaque fills with no texture composited through,
    // but verify against even the textured accent assumption.
    const ratio = contrastRatio(hexToRgb("#0C0F14"), hexToRgb(ACCENT));
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });
});
