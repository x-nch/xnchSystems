# MCP Protocol Ecosystem — Findings (researched 2026-08-24)

**Scope:** spec revisions since 2024-11-05; changes relevant to a Python FastAPI multi-agent
system using stdio MCP servers, possibly adding HTTP transports.
**Method:** 5 web calls — 2 web searches + direct fetches of modelcontextprotocol.io changelog
(2026-07-28, 2025-11-25), security best practices, and registry pages. All claims below cite
official modelcontextprotocol.io / github.com/modelcontextprotocol sources unless marked.

## 1. Revision timeline

| Date | Status | Note |
|---|---|---|
| 2024-11-05 | stable | first stable revision |
| 2025-03-26 | stable | Streamable HTTP + OAuth authorization introduced |
| 2025-06-18 | stable | resource indicators, tool annotations era |
| 2025-11-25 | stable | RC 2025-11-15, released on MCP's first anniversary |
| **2026-07-28** | **latest stable** | RC 2026-07-10, final release 2026-07-28 |

Sources: https://github.com/modelcontextprotocol/modelcontextprotocol/releases (accessed
2026-08-24); https://modelcontextprotocol.io/specification/2026-07-28/changelog;
https://blog.modelcontextprotocol.io/posts/sdk-betas-2026-07-28 ("The new protocol specification
will be launched on July 28, 2026"). No revision newer than 2026-07-28 exists as of 2026-08-24;
the draft changelog shows post-release changes accumulating at
https://modelcontextprotocol.io/specification/draft/changelog.

## 2. Changes in 2025-11-25 (since 2025-06-18)

Source: https://modelcontextprotocol.io/specification/2025-11-25/changelog (accessed 2026-08-24)
- Auth: OIDC Discovery support for auth-server discovery (#797); incremental scope consent via
  `WWW-Authenticate` (SEP-835); Client ID Metadata Documents (CIMD) added as *recommended*
  client-registration mechanism (SEP-991); Protected Resource Metadata discovery aligned with
  RFC 9728, "`WWW-Authenticate` header optional with fallback to `.well-known` endpoint" (SEP-985).
  Token audience binding itself dates to 2025-06-18 and is enforced via the token-passthrough ban:
  servers "MUST NOT accept any tokens that were not explicitly issued for the MCP server"
  (security_best_practices).
- Elicitation: URL-mode elicitation added (SEP-1036); richer enum schemas + defaults (SEP-1330/1034).
- Sampling: tool calling support (`tools`, `toolChoice`) added (SEP-1577).
- Tasks: experimental durable-request tracking with polling (SEP-1686).
- Misc: JSON Schema 2020-12 default dialect; HTTP 403 for invalid Origin headers in Streamable
  HTTP (#1439); stdio servers may log all types to stderr (#670); formal governance + SDK tiers.
- Governance: MCP operates under Linux Foundation ("a Series of LF Projects, LLC", site footer).

## 3. Changes in 2026-07-28 (since 2025-11-25) — BREAKING overhaul

Source: https://modelcontextprotocol.io/specification/2026-07-28/changelog (accessed 2026-08-24)
1. "Remove protocol-level sessions and the `Mcp-Session-Id` header from the Streamable HTTP
   transport" (SEP-2567). Cross-call state = server-minted handles passed as tool arguments.
2. Stateless protocol: "remove the `initialize`/`notifications/initialized` handshake". Every
   request carries version + client capabilities in `_meta`; mismatch →
   `UnsupportedProtocolVersionError` (SEP-2575).
3. New `server/discover` RPC: clients "MAY call it before any other request for up-front version
   selection, or use it as a backward-compatibility probe on STDIO".
4. `subscriptions/listen` (long-lived POST stream) replaces HTTP GET endpoint +
   resources/subscribe; removed SSE resumability (`Last-Event-ID`); broken streams must re-issue.
5. Removed `ping`, `logging/setLevel`, `notifications/roots/list_changed`; per-request log level
   via `_meta`.
6. Tasks moved to official extension `io.modelcontextprotocol/tasks`; `tasks/get` polling +
   `tasks/update`; unsolicited task handles allowed (SEP-2663).
7. Multi Round-Trip Requests (MRTR, SEP-2322) replace server-initiated requests
   (`roots/list`, `sampling/createMessage`, `elicitation/create`): server returns
   `InputRequiredResult` with `inputRequests`; client retries original request with
   `inputResponses`. All results carry required `resultType` ("complete"/"input_required").
8. Deprecations (min 12-month removal window, new lifecycle policy SEP-2596): Roots, Sampling,
   Logging features (SEP-2577); HTTP+SSE transport reclassified Deprecated (migrate to Streamable
   HTTP); OAuth DCR RFC 7591 deprecated in favor of CIMD (#2858); includeContext values.
9. Minor: required `Mcp-Method`/`Mcp-Name` headers on Streamable HTTP POSTs + `x-mcp-header`
   custom headers from tool params (SEP-2243); `CacheableResult` (`ttlMs`, `cacheScope`) on list
   results (SEP-2549); deterministic `tools/list` ordering for prompt-cache hits; RFC 9207 `iss`
   param MUST be validated by clients (SEP-2468); credentials keyed by issuer, no cross-AS reuse
   (SEP-2352); error-code range allocation (-32020..-32099 reserved for spec).
10. SDKs: Python v2.0.0 stable 2026-07-28 (auto version-negotiation, OTel tracing default,
    hardened stdio; v1.x = maintenance line, pin `mcp>=1.27,<2` if you depend on v1);
    TypeScript v2 beta; Go/C# betas. Sources: python-sdk releases v2.0.0/v1.29.0 (via
    releasebot.io/updates/modelcontextprotocol, 2026-07-29); blog.sdk-betas-2026-07-28.
    Back-compat: new clients fall back to the initialize handshake against ≤2025-11-25 servers.

## 4. Registry / signed servers

Source: https://modelcontextprotocol.io/registry/about + https://github.com/modelcontextprotocol/registry
- Official MCP Registry launched in preview 2025-09-08; API frozen at v0.1 on 2025-10-24; live at
  https://registry.modelcontextprotocol.io with active listings updated 2026-08-23 (site fetched).
  Still flagged preview: "Breaking changes or data resets may occur before general availability."
- Metadata format is standardized `server.json` (name, location, install instructions).
- Verification is **namespace ownership**, not artifact signing: GitHub OAuth/OIDC for
  `io.github.username/*`, DNS TXT or HTTP challenge for domain namespaces. No cryptographic
  signing of packages found anywhere in official docs — treat "signed servers" as NOT YET a thing
  (confidence: medium-high; gap noted).

## 5. Operating local MCP servers in multi-agent setups (directly relevant)

Source: https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices
(accessed 2026-08-24)
- **Local MCP Server Compromise**: clients doing one-click config "MUST implement proper consent
  mechanisms prior to executing commands", show exact command untruncated; sandbox spawned
  processes; warn on `sudo`/`rm -rf`/home-dir access.
- For locally-run servers over HTTP: "Require an authorization token" or "Use unix domain sockets
  or other Interprocess Communication (IPC) mechanisms with restricted access"; stdio preferred:
  "Use the `stdio` transport to limit access to just the MCP client."
- **stdio proxy escalation**: if your orchestrator spawns stdio servers as child processes behind
  a proxy service, XSS/token-theft on the client becomes RCE via process spawning — sandbox the
  proxy, restrict FS/network of children, log all spawn events.
- **Localhost redirect URI impersonation**: CIMD proves domain control but not which local process
  owns a localhost port; auth servers should warn on localhost-only redirects and display the
  redirect hostname. Loopback `http://` redirect URIs are the sole HTTPS exception per OAuth 2.1 §1.5.
- SSRF guidance for agents fetching OAuth metadata URLs: block private/link-local ranges except
  explicit dev loopback (RFC 9728 §7.7 cited); beware DNS rebinding/TOCTOU; egress proxies advised.
- New attack surface from statelessness: **State Handle Hijacking** — never treat handle possession
  as auth; bind handles server-side to verified user id; use secure-random expiring handles.
- Mix-up attacks mitigated by RFC 9207 `iss` validation (mandatory for clients now).

## Gaps
- Did not fetch full 2026-07-28 transport/authorization normative text (changelog + security page
  only); exact header semantics worth verifying before implementing HTTP transport.
- No evidence located of registry-side package signing; if needed, verify against registry repo
  issues before relying on absence.
