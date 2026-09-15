/**
 * Hybrid-B gateway gate (docs/superpowers/specs/2026-08-22-workflows-backend-design.md §4):
 * writes to /workflows/* and /approvals/* carry a short-lived HMAC token so a
 * client-forged role header alone cannot decide approvals.
 */
export const GATED_PREFIXES = ["workflows", "approvals", "agents"];

/**
 * Which proxied paths require a minted X-Gateway-Token. Since the
 * 2026-08-24 audit, reads on gated prefixes are gated too: agent-run
 * detail carries raw model output. Chat/SSE/system traffic stays open.
 *
 * Lives outside the route module so `next build` route-type checks (which
 * reject non-HTTP exports) stay clean while the contract test can import it.
 */
export function isGatedGatewayPath(path: string[], method: string): boolean {
  return (
    GATED_PREFIXES.includes(path[0] ?? "") &&
    !["HEAD", "OPTIONS"].includes(method.toUpperCase())
  );
}