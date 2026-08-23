# Research Plan: MCP / Skills / Tools Ecosystem (Aug 2026)

## Main question
What is the current state of the MCP/agent-tooling ecosystem, and what should xnchSystems adopt, fix, or reject — read through this system's specific constraints: local-first, HITL-gated, solo-operated, no silent external inference routing, live unattended auto-dispatch path.

## Subtopics

### 1. MCP protocol current state
- Latest spec revision + notable/breaking changes since mid-2025 review
- Auth model changes (OAuth 2.1, protected resource metadata), transport changes (stdio / streamable HTTP)
- Relevance to a locally-hosted multi-agent system

### 2. MCP server & agent tool-calling security patterns
- Tool-description prompt injection ("tool poisoning"), rug-pull redefinition, cross-server shadowing
- Confused-deputy risk from over-broad tool scopes; supply-chain risk in third-party servers
- Known incidents/CVEs and mitigation patterns (allowlists, approval gates, scanners)
- Lens: this project has real history of unauthenticated LAN surfaces + over-permissive auto-approve

### 3. OpenCode (dispatched coding agent) releases since last review
- New flags, permission-model/safety-default changes
- Status of dangerous-skip-permissions-equivalents and credential exposure surface

## Expected info per subtopic
Each findings file: key facts with dates, source URLs, direct quotes where load-bearing.

## Synthesis
Fold into Part 3 of the audit doc: fixes ranked above new capabilities; explicit rejected-with-reason list.
