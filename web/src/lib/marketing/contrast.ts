/**
 * WCAG 2.x contrast math + compositing of the noise treatment layers.
 * Pure functions — used by contrast.test.ts to verify constraint 3 for real
 * instead of estimating it.
 */

export type Rgb = { r: number; g: number; b: number };

/** #RRGGBB → channels in [0,1] */
export function hexToRgb(hex: string): Rgb {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) throw new Error(`Invalid hex color: ${hex}`);
  const n = parseInt(m[1], 16);
  return {
    r: ((n >> 16) & 0xff) / 255,
    g: ((n >> 8) & 0xff) / 255,
    b: (n & 0xff) / 255,
  };
}

/** WCAG 2.x relative luminance */
export function relLuminance(c: Rgb): number {
  const lin = (v: number) =>
    v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  return (
    0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b)
  );
}

export function contrastRatio(fg: Rgb, bg: Rgb): number {
  const l1 = relLuminance(fg);
  const l2 = relLuminance(bg);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/** W3C compositing spec: overlay blend = hard-light with swapped operands. */
export function overlayBlend(cb: Rgb, cs: Rgb): Rgb {
  const hardLight = (b: number, s: number): number =>
    s <= 0.5 ? 2 * b * s : 1 - 2 * (1 - b) * (1 - s);
  // overlay(backdrop, source) === hardlight(source, backdrop)
  return {
    r: hardLight(cb.r, cs.r),
    g: hardLight(cb.g, cs.g),
    b: hardLight(cb.b, cs.b),
  };
}

function mix(a: number, b: number, t: number): number {
  return a * (1 - t) + b * t;
}

/** Composite `src` over `dst` at alpha (simple alpha compositing). */
export function alphaOver(dst: Rgb, src: Rgb, alpha: number): Rgb {
  return {
    r: mix(dst.r, src.r, alpha),
    g: mix(dst.g, src.g, alpha),
    b: mix(dst.b, src.b, alpha),
  };
}

const WHITE: Rgb = { r: 1, g: 1, b: 1 };

/**
 * Worst-case background a text pixel can sit on:
 * base → grain layer (white-source overlay blend @ --mkt-noise-opacity)
 *      → scanline (white @ --mkt-scanline-opacity).
 * Vignette only darkens edges, which raises contrast for light text —
 * omitted as the conservative direction.
 */
export function worstCaseBackground(
  baseHex: string,
  grainOpacity = 0.05,
  scanlineAlpha = 0.04,
): Rgb {
  const base = hexToRgb(baseHex);
  const grained = alphaOver(base, overlayBlend(base, WHITE), grainOpacity);
  return alphaOver(grained, WHITE, scanlineAlpha);
}
