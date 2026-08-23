import { NextResponse, type NextRequest } from "next/server";
import { createHmac } from "crypto";

const DEFAULT_GATEWAY = "http://192.168.1.10:8001";

/** Vercel Pro — long enough for SSE chat/graph through the tunnel proxy. */
export const maxDuration = 300;

/**
 * Hybrid-B gateway gate (docs/superpowers/specs/2026-08-22-workflows-backend-design.md §4):
 * writes to /workflows/* and /approvals/* carry a short-lived HMAC token so a
 * client-forged role header alone cannot decide approvals.
 */
const GATED_PREFIXES = ["workflows", "approvals"];

function mintGatewayToken(secret: string, ttlS = 300): string {
  const expiry = String(Math.floor(Date.now() / 1000) + ttlS);
  const sig = createHmac("sha256", secret).update(expiry).digest("hex");
  return `${expiry}.${sig}`;
}

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

/**
 * Thin server-side proxy to the xnch gateway (:8001).
 *
 * The browser only ever talks to this same-origin route, so there is no CORS
 * and SSE streams pass through untouched. Point it at another host with the
 * XNCH_GATEWAY_URL env var.
 */
export async function proxyGateway(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const gateway = process.env.XNCH_GATEWAY_URL ?? DEFAULT_GATEWAY;

  const upstream = new URL(`/${path.join("/")}`, gateway);
  upstream.search = request.nextUrl.search;

  const headers = buildUpstreamHeaders(request);
  const method = request.method.toUpperCase();

  const gatewaySecret = process.env.XNCH_GATEWAY_SECRET ?? "";
  const isGated =
    GATED_PREFIXES.includes(path[0] ?? "") &&
    !["GET", "HEAD", "OPTIONS"].includes(method);
  if (gatewaySecret && isGated) {
    headers.set("X-Gateway-Token", mintGatewayToken(gatewaySecret));
  }

  let body: BodyInit | null = null;
  if (method !== "GET" && method !== "HEAD" && request.body) {
    body = request.body as unknown as BodyInit;
  }

  try {
    const upstreamResp = await fetch(upstream, {
      method,
      headers,
      body,
      // @ts-expect-error — Node fetch requires duplex for streaming request bodies
      duplex: body ? "half" : undefined,
      cache: "no-store",
      redirect: "manual",
    });

    const responseHeaders = new Headers();
    for (const [key, value] of upstreamResp.headers.entries()) {
      if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
      if (key.toLowerCase() === "content-length") continue;
      responseHeaders.set(key, value);
    }
    responseHeaders.set("x-gateway-proxy", "next");

    return new NextResponse(upstreamResp.body, {
      status: upstreamResp.status,
      statusText: upstreamResp.statusText,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach xnch gateway at ${gateway}` },
      { status: 502 }
    );
  }
}

function buildUpstreamHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  for (const [key, value] of request.headers.entries()) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
    if (key.toLowerCase() === "host") continue;
    headers.set(key, value);
  }

  // Cloudflare Access service token (Vercel → api.x-nch.com behind Access).
  const cfClientId = process.env.CF_ACCESS_CLIENT_ID;
  const cfClientSecret = process.env.CF_ACCESS_CLIENT_SECRET;
  if (cfClientId && cfClientSecret) {
    headers.set("CF-Access-Client-Id", cfClientId);
    headers.set("CF-Access-Client-Secret", cfClientSecret);
  }

  return headers;
}

export const GET = proxyGateway;
export const POST = proxyGateway;
export const PUT = proxyGateway;
export const PATCH = proxyGateway;
export const DELETE = proxyGateway;
export const OPTIONS = proxyGateway;
