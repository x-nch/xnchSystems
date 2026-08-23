# MCP Server & Agent Tool-Calling Security — Findings as of 2026-08-24

**Lens:** solo-operated, local-first, HITL-gated system with known history of (a) unauthenticated services reachable on LAN, (b) auto-approve gateway flag with no allowlist.
**Method:** 4 web searches; ~25 sources consulted, 3 discarded (thin vendor marketing). All URLs accessed 2026-08-24. Confidence tagged (high = ≥2 independent credible sources; med = single credible source).

## 1. Tool-description prompt injection ("tool poisoning")
- Mechanics: clients inject **all** connected servers' tool descriptions into model context; models treat them as authoritative as system prompts — no instruction/data boundary. Structural, not vendor-specific. (high) https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-ai-agent-exfiltration-2
- Named + demonstrated by Invariant Labs, **April 1, 2025** (often misdated March): benign `add` tool hid instructions to read `~/.ssh/id_rsa` + `claude_desktop_config.json` and exfiltrate via another tool's innocuous `context` param; Cursor's approval dialog hid full arguments. Follow-ups: WhatsApp chat-history exfiltration (Apr 7, 2025); private-repo exfil via poisoned GitHub issue. (high) https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks · PoC code: https://github.com/invariantlabs-ai/mcp-injection-experiments
- Line-jumping: Trail of Bits showed payloads fire **before first tool use**, at connection/context-load time. (high) https://blog.trailofbits.com/2025/04/21/jumping-the-line-how-mcp-servers-can-attack-you-before-you-ever-use-them/
- Hidden-instruction variants: invisible Unicode Tag codepoints (human sees nothing, model reads commands — Rehberger); ANSI-escape hiding (Brightsec disclosure). (med–high) https://www.speakeasy.com/resources/mcp-tool-poisoning · https://embracethered.com/blog/posts/2026/scary-agent-skills/
- Scale: MCPTox benchmark (arXiv 2508.14925, Aug 2025) — >60% attack success across 45 real servers, best model 72.8%. (med–high) https://arxiv.org/html/2508.14925v1

## 2. Rug pulls & cross-server shadowing (confused deputy)
- **Rug pull:** server silently changes tool definition after initial approval; approval doesn't re-trigger. Formalized as CVE-2025-54136 ("MCPoison", Cursor IDE, CVSS 8.8, Check Point Jul 2025, patched 1.3): attacker commits benign `.cursor/mcp.json`, waits for approval, swaps it — payload runs on every launch. (high) https://nvd.nist.gov/vuln/detail/CVE-2025-54136 · https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks
- **Tool shadowing / cross-server escalation:** a malicious server can't call other servers' tools directly, but its description instructs the agent to abuse trusted ones (e.g., "forward messages via WhatsApp server to <number>") — cross-origin confused deputy. Requires no access to the target tool. (high) CSA link above · https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html
- **Confused deputy generally:** server acts with its own broad privileges, not the user's. (high) OWASP cheat sheet above.
- Proposed protocol fix (not deployed mainstream): ETDI — signed/versioned tool definitions. (med) https://arxiv.org/html/2506.01333v1
- Defense pattern: hash-pin tool definitions, re-verify every session, alert on change (mcp-scan does this). (high) https://www.practical-devsecops.com/top-mcp-security-tools/

## 3. Supply chain (npm/PyPI/Docker)
- **postmark-mcp backdoor — first in-the-wild malicious MCP server** (Sept 2025): typosquat/impersonation on npm; 15 clean versions, then v1.0.16+ BCC'd every outbound email to attacker inbox; ~1.5k weekly installs; removed by Sep 25; Postmark published advisory; legit repo NOT breached. (high) https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/ · https://postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package · https://www.theregister.com/2025/09/29/postmark_mcp_server_code_hijacked
- **SANDWORM_MODE npm worm** (Socket, Feb 20 2026): 19+ typosquatted packages install rogue MCP server into Claude Desktop/Cursor/VS Code Continue/Windsurf configs; harvest SSH keys, cloud creds, LLM API keys. (med–high) https://socket.dev/blog/sandworm-mode-npm-worm-ai-toolchain-poisoning · roundup incl. Shai-Hulud/Shai-Hulud 2.0/Mastra(@mastra, Jun 2026): https://mcp.directory/blog/npm-supply-chain-attacks-mcp-2026
- Exposure data: Trend Micro found **492 MCP servers exposed to the public internet with zero auth**; only ~8.5% of public servers use OAuth; GitGuardian: 24,008 secrets in public MCP configs, 2,117 still valid. (med, aggregated) https://www.practical-devsecops.com/mcp-security-statistics-2026-report
- Docker/registry layer less documented than npm — gap. TruffleHog can scan Docker images for leaked secrets.

## 4. Over-broad scopes → mitigations
- Over-scoped OAuth (full mailbox vs read-only) makes one compromised server a breach path to everything it touches; least-privilege per resource, narrow scopes, short-lived tokens, governable agent identity. (high) https://techcommunity.microsoft.com/blog/microsoft-security-blog/the-state-of-mcp-security-in-2026/4531327
- **Spec tool annotations** (2025-06-18 rev): `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` — advisory metadata for clients to gate approvals/UI. Not enforced by protocol; client must act on them. (high) https://modelcontextprotocol.io/specification/2025-06-18
- Human-in-the-loop: NSA AI Security Center CSI on MCP (Jun 2026) flags weak approval workflows; recommends trust boundaries, sandboxed execution, output filtering on chains, full invocation logging. (high) https://media.defense.gov/2026/Jun/02/2003943289/-1/-1/0/CSI_MCP_SECURITY.PDF
- Auto-run/auto-approve is the multiplier: with auto-approve, injected instructions get the agent's full tool access with zero interaction. (high) https://www.elastic.co/security-labs/mcp-tools-attack-defense-recommendations
- Allowlists + secret isolation: curated approved-server list; deny-by-default; secrets kept out of agent-readable context (env files, configs are first exfil target — Invariant PoC). (high) OWASP cheat sheet · policylayer.com/attacks/mcp-typosquatting
- Framing taxonomy: OWASP MCP Top 10 (beta Apr 2026): MCP01 secrets, MCP02 scope creep, MCP03 tool poisoning, MCP04 supply chain, MCP05 command injection, MCP07 authn/z, MCP09 shadow servers… (high) https://owasp.org/www-project-mcp-top-10/

## 5. Defense/scanning tooling current as of 2026
- **mcp-scan (Invariant → Snyk "agent-scan")**: open-source, 2k+ stars; detects tool poisoning, rug pulls (hash pinning), cross-origin escalation across Claude Desktop/Cursor/Claude Code/Gemini CLI/Windsurf; `uvx mcp-scan@latest`. Still the default first run. (high) https://www.practical-devsecops.com/top-mcp-security-tools/
- Others: Cisco mcp-scanner (YARA + LLM judge); Golf scanner (Go, 20 checks, 7 IDEs); mcp-sec-audit (100% on MCPTox); Backslash, Promptfoo; community: github.com/cc-fuyu/mcp-security-scan (Feb 2026), shanefirek/mcp-security-scanner (maps to NSA guidance). Academic comparison: ACM MCP-Scanner survey. (med–high) same URLs + https://github.com/cc-fuyu/mcp-security-scan
- Caveat: YARA-only scanners measured at ~78% false-positive rate (AppSec Santa, Apr 2026) — pair static scan with review. (med) https://www.practical-devsecops.com/mcp-security-statistics-2026-report
- **gitleaks** and **trufflehog**: both actively maintained and standard in 2026; TruffleHog adds live verification + Docker image scanning; use both for repo/config/image secrets. (high) https://github.com/trufflesecurity/trufflehog · https://github.com/gitleaks/gitleaks · https://www.kali.org/tools/trufflehog
- Gateways/runtime inspection exist (Docker MCP Gateway, MintMCP, Pipelock, Lasso) but are heavier than a solo local-first setup needs. (med)

## 6. Notable CVEs / incidents 2025–2026
- **CVE-2025-49596** (CVSS 9.4): MCP Inspector RCE — proxy lacked auth; browser/DNS-rebinding hit localhost dev tool; fixed 0.14.1 Jun 13 2025. "localhost ≠ safe." (high) https://www.oligo.security/blog/critical-rce-vulnerability-in-anthropic-mcp-inspector-cve-2025-49596
- **CVE-2025-6514** (9.6): mcp-remote OS command injection via untrusted remote server's OAuth values; 437k+ downloads; fixed 0.1.16. (high) https://research.jfrog.com/vulnerabilities/mcp-remote-command-injection-rce-jfsa-2025-001290844/
- **CVE-2025-54136** (8.8): Cursor MCPoison rug pull (see §2). (high)
- **CVE-2026-23744**: MCPJam inspector ≤1.4.2 RCE — **binds 0.0.0.0 by default**, crafted HTTP request triggers server install → RCE. Directly mirrors your LAN-unauthenticated-services class. (med–high) https://github.com/ibreakthingsforaliving/CVE-2026-23744-PoC · https://vulnerablemcp.info/
- **CVE-2025-68144**: Git MCP server arg injection (`--output=` arbitrary file write) chained with Filesystem MCP into RCE. (med) https://pipelab.org/blog/state-of-mcp-security-2026
- Also: CVE-2025-11286 (MCPHub cmd injection), CVE-2025-10193 (Neo4j Cypher server authz), CVE-2026-0621 (TS SDK ReDoS); running tracker: https://github.com/mcp-security-project/mcp-cve-project (218+ entries). (med)
- Non-CVE incidents: **GitHub MCP toxic-agent-flow** (malicious public-repo issue leaks private repos, Invariant); **Supabase MCP lethal-trifecta** (service-role agent + ticket injection → token exfiltration); **Asana MCP cross-tenant leak** (tenant-isolation defect). (high) https://safeguard.sh/resources/blog/analysis-of-known-mcp-server-cves-and-disclosed-vulnerabilities · https://www.pomerium.com/blog/when-ai-has-root-lessons-from-the-supabase-mcp-data-leak
- Single-source, verify before relying: zero-click prompt-injection CVEs 2026-22252/2026-22688; MS CVE-2026-26118 (Mar 2026 Patch Tuesday); CSA "design-level RCE across official SDKs" (Apr 2026). (low–med)

## Mitigations ranked for THIS system (solo, local-first, HITL-gated)
1. **Bind every MCP/dev service to 127.0.0.1, never 0.0.0.0; require auth tokens even on loopback.** Directly addresses the LAN-unauthenticated history; validated by CVE-2025-49596, CVE-2026-23744, Trend Micro's 492 exposed servers.
2. **Kill the blanket auto-approve flag → explicit per-tool allowlist, deny-by-default.** Honor `readOnlyHint`/`destructiveHint`: read-only may auto-run after allowlisting; everything destructive or network-egress-capable stays behind the HITL gate. Auto-approve converts any injection into full agent-privilege compromise.
3. **Hash-pin tool definitions + re-verify every session; alert on any change** (rug-pull defense; mcp-scan supports this). One-time approval is not a control in MCP.
4. **Curated server allowlist + pinned versions in source control** (no floating `@latest` npx/uvx); quarantine new servers 48h before credential access; prefer vendored/first-party servers.
5. **Least-privilege scoping per server:** read-only where possible; short-lived scoped tokens; one credential set per server so one compromise ≠ everything.
6. **Secret isolation:** keep `.env`, API keys, and other MCP servers' configs out of agent-reachable paths; they're the #1 exfil target (Invariant PoC). Run `gitleaks` + `trufflehog` (incl. filesystem/docker modes) over configs periodically.
7. **Scan on change:** run mcp-scan/Snyk agent-scan against configs and tool descriptions on every session start, not only at install time (descriptions can change server-side).
8. **Log every tool call + argument** to append-only audit trail (your existing audit-event pattern); alert on anomalous destinations/params containing credential-shaped strings.
9. Egress allowlist for agent-initiated network calls; segment the dev host from other LAN devices (limits blast radius of any single compromised server).

---
*Queries used:* (1) `"tool poisoning" MCP Invariant Labs cross-server shadowing rug pull` [failed via firecrawl, rerun]; (2) `malicious MCP server npm supply chain typosquatting "postmark-mcp" backdoor`; (3) `MCP CVE 2025 2026 "MCP Inspector"/"mcp-remote"/GitHub MCP prompt injection`; (4) `MCP security scanner 2026 mcp-scan gitleaks trufflehof audit annotations least privilege` (typo-tolerant); (5) `"tool poisoning" hidden instructions "line jumps" rug pull confused deputy readOnlyHint`. Gaps: PyPI-side MCP incidents under-documented vs npm; Docker registry MCP malware thin; several 2026 CVEs single-source.
