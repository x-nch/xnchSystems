import { NextResponse, type NextRequest } from "next/server";

const DEFAULT_MEDIA_GATEWAY = "http://192.168.1.9:8090";

/** Media files are large (video up to 200MB) — keep the route alive. */
export const maxDuration = 300;

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
 * Server-side proxy to the Node B media-gateway (:8090).
 *
 * The browser only ever talks to this same-origin route, so there is no CORS
 * and the bearer token stays out of the browser. The media token is injected
 * here from MEDIA_GATEWAY_TOKEN; the upstream address comes from
 * MEDIA_GATEWAY_URL. Multipart upload bodies pass through untouched.
 */
async function proxyMedia(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const gateway = process.env.MEDIA_GATEWAY_URL ?? DEFAULT_MEDIA_GATEWAY;
  const token = process.env.MEDIA_GATEWAY_TOKEN;

  const upstream = new URL(`/${path.join("/")}`, gateway);
  upstream.search = request.nextUrl.search;

  const headers = buildUpstreamHeaders(request);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let body: BodyInit | null = null;
  const method = request.method.toUpperCase();
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
    responseHeaders.set("x-media-proxy", "next");

    return new NextResponse(upstreamResp.body, {
      status: upstreamResp.status,
      statusText: upstreamResp.statusText,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach media gateway at ${gateway}` },
      { status: 502 }
    );
  }
}

function buildUpstreamHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  for (const [key, value] of request.headers.entries()) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
    if (key.toLowerCase() === "host") continue;
    if (key.toLowerCase() === "authorization") continue;
    headers.set(key, value);
  }
  return headers;
}

export const GET = proxyMedia;
export const POST = proxyMedia;
export const PUT = proxyMedia;
export const PATCH = proxyMedia;
export const DELETE = proxyMedia;
export const OPTIONS = proxyMedia;
