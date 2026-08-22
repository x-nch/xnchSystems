import { SignJWT } from "jose";

export type AuthMode = "actor" | "jwt" | "token";

export interface AuthConfig {
  mode: AuthMode;
  /** Identity used for `actor:<id>` dev auth and as JWT `sub`. */
  actorId: string;
  /** Shared secret used to mint HS256 JWTs (mirrors CLI XNCH_AUTH_SECRET). */
  authSecret: string;
  /** Pre-signed bearer token pasted by the user. */
  pastedToken: string;
}

/**
 * Build an Authorization header value that xnch's TokenVerifier accepts:
 *   - `actor:<id>`   (dev mode, accepted verbatim)
 *   - `Bearer <hs256-jwt>` signed with the shared auth secret (matches the CLI)
 *   - `Bearer <pasted token>`
 */
export async function buildAuthorization(config: AuthConfig): Promise<string | null> {
  switch (config.mode) {
    case "actor":
      return `actor:${config.actorId || "operator"}`;
    case "jwt":
      if (!config.authSecret) return null;
      return mintHs256Token(config);
    case "token":
      if (!config.pastedToken) return null;
      return config.pastedToken.startsWith("Bearer ")
        ? config.pastedToken
        : `Bearer ${config.pastedToken}`;
    default:
      return null;
  }
}

async function mintHs256Token(config: AuthConfig): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const secret = new TextEncoder().encode(config.authSecret);
  return new SignJWT({ sub: config.actorId || "operator", iss: "xnch" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt(now)
    .setExpirationTime(now + 3600)
    .sign(secret);
}

/** Short human-readable label for the topbar chip. */
export function authModeLabel(mode: AuthMode): string {
  switch (mode) {
    case "actor":
      return "dev actor";
    case "jwt":
      return "minted JWT";
    case "token":
      return "bearer token";
  }
}
